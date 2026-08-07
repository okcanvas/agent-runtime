from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


class PostgreSQLDriverUnavailable(RuntimeError):
    """Raised when the optional PostgreSQL driver is unavailable."""


class PostgreSQLConnectionError(RuntimeError):
    """Safe connection failure that never includes a DSN or driver payload."""


@dataclass(frozen=True)
class PostgreSQLConnectionSettings:
    dsn: str = field(repr=False)
    connect_timeout_seconds: int = 15
    application_name: str = "okcanvas-agent-runtime"

    def __post_init__(self) -> None:
        value = self.dsn.strip()
        if not value or not value.lower().startswith(("postgresql://", "postgres://")):
            raise ValueError("PostgreSQL DSN must use postgres:// or postgresql://")
        if not 1 <= self.connect_timeout_seconds <= 120:
            raise ValueError("PostgreSQL connect timeout must be 1..120 seconds")
        if not self.application_name.strip() or len(self.application_name) > 128:
            raise ValueError("PostgreSQL application name is invalid")
        object.__setattr__(self, "dsn", value)
        object.__setattr__(self, "application_name", self.application_name.strip())

    @property
    def dsn_sha256(self) -> str:
        return hashlib.sha256(self.dsn.encode("utf-8")).hexdigest()

    def __repr__(self) -> str:
        return (
            "PostgreSQLConnectionSettings("
            f"dsn='[REDACTED]', connect_timeout_seconds={self.connect_timeout_seconds}, "
            f"application_name={self.application_name!r})"
        )


class HybridRow(Mapping[str, Any]):
    """SQLite-row-compatible mapping that also supports positional indexing."""

    def __init__(self, columns: Sequence[str], values: Sequence[Any]) -> None:
        self._columns = tuple(columns)
        self._values = tuple(values)
        self._mapping = dict(zip(self._columns, self._values, strict=True))

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return self._mapping[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._columns)

    def __len__(self) -> int:
        return len(self._columns)

    def keys(self) -> tuple[str, ...]:
        return self._columns


class PostgreSQLCursorAdapter:
    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor

    @property
    def rowcount(self) -> int:
        value = getattr(self._cursor, "rowcount", -1)
        return int(value if value is not None else -1)

    def _columns(self) -> tuple[str, ...]:
        description = getattr(self._cursor, "description", None) or ()
        result: list[str] = []
        for item in description:
            name = getattr(item, "name", None)
            if name is None and isinstance(item, Sequence) and item:
                name = item[0]
            result.append(str(name))
        return tuple(result)

    def _row(self, value: Any) -> HybridRow | None:
        if value is None:
            return None
        if isinstance(value, Mapping):
            columns = tuple(str(key) for key in value.keys())
            return HybridRow(columns, tuple(value[key] for key in value.keys()))
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise TypeError("PostgreSQL cursor returned an unsupported row shape")
        return HybridRow(self._columns(), value)

    def fetchone(self) -> HybridRow | None:
        return self._row(self._cursor.fetchone())

    def fetchall(self) -> list[HybridRow]:
        return [row for value in self._cursor.fetchall() if (row := self._row(value)) is not None]


ConnectFactory = Callable[[PostgreSQLConnectionSettings], Any]


def _default_connect(settings: PostgreSQLConnectionSettings) -> Any:
    try:
        import psycopg  # type: ignore[import-not-found]
    except ImportError as exc:
        raise PostgreSQLDriverUnavailable(
            "PostgreSQL backend requires the optional psycopg package"
        ) from exc
    try:
        connection = psycopg.connect(
            settings.dsn,
            connect_timeout=settings.connect_timeout_seconds,
            application_name=settings.application_name,
        )
        connection.autocommit = True
        return connection
    except Exception as exc:  # pragma: no cover - real driver/live path
        raise PostgreSQLConnectionError("PostgreSQL connection could not be established") from exc


def _translate_qmark_sql(sql: str) -> str:
    stripped = sql.strip()
    if stripped.upper() == "BEGIN IMMEDIATE":
        return "BEGIN"
    result: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(sql):
        char = sql[index]
        if quote is not None:
            result.append(char)
            if char == quote:
                if index + 1 < len(sql) and sql[index + 1] == quote:
                    result.append(sql[index + 1])
                    index += 1
                else:
                    quote = None
        elif char in {"'", '"'}:
            quote = char
            result.append(char)
        elif char == "?":
            result.append("%s")
        else:
            result.append(char)
        index += 1
    return "".join(result)


def _split_sql_script(script: str) -> tuple[str, ...]:
    statements: list[str] = []
    current: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(script):
        char = script[index]
        if quote is not None:
            current.append(char)
            if char == quote:
                if index + 1 < len(script) and script[index + 1] == quote:
                    current.append(script[index + 1])
                    index += 1
                else:
                    quote = None
        elif char in {"'", '"'}:
            quote = char
            current.append(char)
        elif char == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(char)
        index += 1
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return tuple(statements)


def _is_integrity_error(exc: Exception) -> bool:
    sqlstate = str(getattr(exc, "sqlstate", ""))
    if sqlstate.startswith("23"):
        return True
    return exc.__class__.__name__.lower() in {
        "integrityerror",
        "uniqueviolation",
        "foreignkeyviolation",
        "checkviolation",
        "notnullviolation",
    }


class PostgreSQLConnectionAdapter:
    _ROW_LOCK_PREFIXES = (
        "SELECT STATUS FROM TASK WHERE TASK_ID",
        "SELECT * FROM TASK WHERE TASK_ID",
        "SELECT STATE FROM AGENT_INVOCATION WHERE INVOCATION_ID",
        "SELECT * FROM AGENT_INVOCATION WHERE INVOCATION_ID",
        "SELECT STATUS FROM RUN WHERE RUN_ID",
        "SELECT 1 FROM RUN WHERE RUN_ID",
        "SELECT * FROM SERVICE_RESOURCE_OWNER WHERE RESOURCE_TYPE",
        "SELECT TENANT_ID,PRINCIPAL_ID FROM SERVICE_RESOURCE_OWNER",
        "SELECT * FROM GOVERNED_TOOL_APPROVAL WHERE APPROVAL_ID",
        "SELECT * FROM GOVERNED_TOOL_APPROVAL WHERE SUBMISSION_ID",
        "SELECT * FROM PRODUCT_SESSION WHERE SESSION_ID",
        "SELECT * FROM PRODUCT_SESSION_KEY_ROTATION WHERE SESSION_ID",
    )

    def __init__(self, raw_connection: Any) -> None:
        self._raw = raw_connection
        self._transaction_active = False
        self._row_factory: Any = None
        if hasattr(self._raw, "autocommit"):
            self._raw.autocommit = True

    @property
    def row_factory(self) -> Any:
        return self._row_factory

    @row_factory.setter
    def row_factory(self, value: Any) -> None:
        # Compatibility surface for SQLite-derived stores. PostgreSQL rows are
        # normalized by PostgreSQLCursorAdapter regardless of this value.
        self._row_factory = value

    def _transaction_sql(self, sql: str, params: Sequence[Any]) -> str:
        translated = _translate_qmark_sql(sql)
        normalized = " ".join(translated.strip().upper().split())
        if normalized == "BEGIN":
            self._transaction_active = True
            return translated
        if (
            self._transaction_active
            and normalized.startswith(self._ROW_LOCK_PREFIXES)
            and " FOR UPDATE" not in normalized
        ):
            return translated.rstrip().rstrip(";") + " FOR UPDATE"
        if (
            self._transaction_active
            and normalized.startswith("SELECT * FROM RUN_SUBMISSION_PREFLIGHT WHERE IDEMPOTENCY_KEY_SHA256")
            and params
        ):
            lock = self._raw.cursor()
            lock.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (params[0],),
            )
        if (
            self._transaction_active
            and (
                normalized.startswith("SELECT COALESCE(MAX(ORDINAL)")
                or normalized.startswith("SELECT COALESCE(MAX(SEQUENCE)")
            )
            and params
        ):
            lock = self._raw.cursor()
            lock.execute("SELECT run_id FROM run WHERE run_id = %s FOR UPDATE", (params[0],))
        return translated

    def execute(self, sql: str, params: Sequence[Any] = ()) -> PostgreSQLCursorAdapter:
        cursor = self._raw.cursor()
        try:
            cursor.execute(self._transaction_sql(sql, params), tuple(params))
        except Exception as exc:
            if _is_integrity_error(exc):
                raise sqlite3.IntegrityError("PostgreSQL integrity constraint failed") from exc
            raise
        return PostgreSQLCursorAdapter(cursor)

    def executescript(self, script: str) -> None:
        for statement in _split_sql_script(script):
            self.execute(statement)

    def commit(self) -> None:
        self._raw.commit()
        self._transaction_active = False

    def rollback(self) -> None:
        self._raw.rollback()
        self._transaction_active = False

    def close(self) -> None:
        self._raw.close()


@contextmanager
def postgresql_connection(
    settings: PostgreSQLConnectionSettings,
    connect_factory: ConnectFactory | None = None,
) -> Iterator[PostgreSQLConnectionAdapter]:
    factory = connect_factory or _default_connect
    try:
        raw = factory(settings)
    except (PostgreSQLDriverUnavailable, PostgreSQLConnectionError):
        raise
    except Exception as exc:
        raise PostgreSQLConnectionError("PostgreSQL connection could not be established") from exc
    connection = PostgreSQLConnectionAdapter(raw)
    try:
        yield connection
    finally:
        connection.close()
