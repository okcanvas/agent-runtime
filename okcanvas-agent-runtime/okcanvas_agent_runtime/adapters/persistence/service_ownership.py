from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from okcanvas_agent_runtime.application.errors import ControlAPIError

from okcanvas_agent_runtime.core.service_identity import ServicePrincipal

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$")
_RESOURCE_TYPES = frozenset({
    "attachment-slot", "project-snapshot-slot", "session", "submission", "task", "run", "approval"
})
_SCHEMA = """
CREATE TABLE IF NOT EXISTS service_resource_owner (
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(resource_type, resource_id)
);
CREATE INDEX IF NOT EXISTS idx_service_resource_owner_principal
ON service_resource_owner(tenant_id, principal_id, resource_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_service_resource_owner_tenant
ON service_resource_owner(tenant_id, resource_type, created_at DESC);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ServiceResourceOwner:
    resource_type: str
    resource_id: str
    tenant_id: str
    principal_id: str
    created_at: str


class SQLiteServiceResourceOwnershipStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=15, isolation_level=None, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=15000")
        connection.execute("PRAGMA journal_mode=WAL")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(_SCHEMA)

    def register(self, *, principal: ServicePrincipal, resource_type: str, resource_id: str) -> ServiceResourceOwner:
        self._validate(resource_type, resource_id)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM service_resource_owner WHERE resource_type=? AND resource_id=?",
                (resource_type, resource_id),
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO service_resource_owner(resource_type,resource_id,tenant_id,principal_id,created_at) VALUES(?,?,?,?,?)",
                    (resource_type, resource_id, principal.tenant_id, principal.principal_id, _now()),
                )
                connection.commit()
            else:
                if row["tenant_id"] != principal.tenant_id or row["principal_id"] != principal.principal_id:
                    connection.rollback()
                    raise ControlAPIError(409, "SERVICE_RESOURCE_OWNERSHIP_CONFLICT", "Resource ownership already belongs to another principal")
                connection.commit()
        return self.get(resource_type=resource_type, resource_id=resource_id)

    def get(self, *, resource_type: str, resource_id: str) -> ServiceResourceOwner:
        self._validate(resource_type, resource_id)
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM service_resource_owner WHERE resource_type=? AND resource_id=?",
                (resource_type, resource_id),
            ).fetchone()
        if row is None:
            raise ControlAPIError(404, "SERVICE_RESOURCE_NOT_FOUND", "Service resource was not found")
        return ServiceResourceOwner(**dict(row))

    def require_principal(self, *, principal: ServicePrincipal, resource_type: str, resource_id: str) -> ServiceResourceOwner:
        owner = self.get(resource_type=resource_type, resource_id=resource_id)
        if owner.tenant_id != principal.tenant_id or owner.principal_id != principal.principal_id:
            raise ControlAPIError(404, "SERVICE_RESOURCE_NOT_FOUND", "Service resource was not found")
        return owner

    def require_tenant(self, *, principal: ServicePrincipal, resource_type: str, resource_id: str) -> ServiceResourceOwner:
        owner = self.get(resource_type=resource_type, resource_id=resource_id)
        if owner.tenant_id != principal.tenant_id:
            raise ControlAPIError(404, "SERVICE_RESOURCE_NOT_FOUND", "Service resource was not found")
        return owner

    def list_ids(self, *, principal: ServicePrincipal, resource_type: str, tenant_wide: bool = False, limit: int = 200) -> tuple[str, ...]:
        if resource_type not in _RESOURCE_TYPES or not 1 <= limit <= 200:
            raise ValueError("Service ownership list query is invalid")
        with self._connection() as connection:
            if tenant_wide:
                rows = connection.execute(
                    "SELECT resource_id FROM service_resource_owner WHERE tenant_id=? AND resource_type=? ORDER BY created_at DESC, resource_id DESC LIMIT ?",
                    (principal.tenant_id, resource_type, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT resource_id FROM service_resource_owner WHERE tenant_id=? AND principal_id=? AND resource_type=? ORDER BY created_at DESC, resource_id DESC LIMIT ?",
                    (principal.tenant_id, principal.principal_id, resource_type, limit),
                ).fetchall()
        return tuple(str(row["resource_id"]) for row in rows)

    def release(self, *, principal: ServicePrincipal, resource_type: str, resource_id: str) -> None:
        self.require_principal(principal=principal, resource_type=resource_type, resource_id=resource_id)
        self.release_if_exists(resource_type=resource_type, resource_id=resource_id)

    def release_if_owned(
        self,
        *,
        principal: ServicePrincipal,
        resource_type: str,
        resource_id: str,
    ) -> bool:
        self._validate(resource_type, resource_id)
        with self._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM service_resource_owner "
                "WHERE resource_type=? AND resource_id=? AND tenant_id=? AND principal_id=?",
                (
                    resource_type,
                    resource_id,
                    principal.tenant_id,
                    principal.principal_id,
                ),
            )
        return cursor.rowcount == 1

    def release_if_exists(self, *, resource_type: str, resource_id: str) -> bool:
        self._validate(resource_type, resource_id)
        with self._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM service_resource_owner WHERE resource_type=? AND resource_id=?",
                (resource_type, resource_id),
            )
        return cursor.rowcount == 1

    @staticmethod
    def _validate(resource_type: str, resource_id: str) -> None:
        if resource_type not in _RESOURCE_TYPES or _ID_RE.fullmatch(resource_id) is None:
            raise ValueError("Service resource identity is invalid")
