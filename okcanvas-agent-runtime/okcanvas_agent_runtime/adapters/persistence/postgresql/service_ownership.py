from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from okcanvas_agent_runtime.adapters.persistence.postgresql.driver import (
    ConnectFactory,
    PostgreSQLConnectionAdapter,
    PostgreSQLConnectionSettings,
    postgresql_connection,
)
from okcanvas_agent_runtime.adapters.persistence.service_ownership import (
    SQLiteServiceResourceOwnershipStore,
    ServiceResourceOwner,
    _SCHEMA,
    _now,
)
from okcanvas_agent_runtime.application.errors import ControlAPIError
from okcanvas_agent_runtime.core.service_identity import ServicePrincipal


class PostgreSQLServiceResourceOwnershipStore(SQLiteServiceResourceOwnershipStore):
    """PostgreSQL service ownership adapter sharing Product admission storage."""

    def __init__(
        self,
        settings: PostgreSQLConnectionSettings,
        *,
        connect_factory: ConnectFactory | None = None,
    ) -> None:
        self.settings = settings
        self._connect_factory = connect_factory

    @contextmanager
    def _connection(self) -> Iterator[PostgreSQLConnectionAdapter]:
        with postgresql_connection(self.settings, self._connect_factory) as connection:
            yield connection

    def initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(_SCHEMA)

    def register(
        self,
        *,
        principal: ServicePrincipal,
        resource_type: str,
        resource_id: str,
    ) -> ServiceResourceOwner:
        self._validate(resource_type, resource_id)
        with self._connection() as connection:
            connection.execute("BEGIN")
            try:
                connection.execute(
                    """
                    INSERT INTO service_resource_owner(
                        resource_type, resource_id, tenant_id, principal_id, created_at
                    ) VALUES(?, ?, ?, ?, ?)
                    ON CONFLICT(resource_type, resource_id) DO NOTHING
                    """,
                    (
                        resource_type,
                        resource_id,
                        principal.tenant_id,
                        principal.principal_id,
                        _now(),
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM service_resource_owner "
                    "WHERE resource_type = ? AND resource_id = ? FOR UPDATE",
                    (resource_type, resource_id),
                ).fetchone()
                if row is None:
                    raise RuntimeError("Service ownership insert did not produce a row")
                if (
                    row["tenant_id"] != principal.tenant_id
                    or row["principal_id"] != principal.principal_id
                ):
                    raise ControlAPIError(
                        409,
                        "SERVICE_RESOURCE_OWNERSHIP_CONFLICT",
                        "Resource ownership already belongs to another principal",
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return ServiceResourceOwner(**dict(row))
