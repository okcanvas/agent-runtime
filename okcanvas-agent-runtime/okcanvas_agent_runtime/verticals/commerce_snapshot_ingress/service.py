from __future__ import annotations

import asyncio
import hashlib
import re
from collections.abc import Mapping

import httpx

from okcanvas_agent_runtime.application.submissions import ProtectedPayloadRetentionState, RunSubmissionAuthorityError, RunSubmissionBoundaryService, RunSubmissionDecision, RunSubmissionIdempotencyConflict, RunSubmissionRecordState, RunSubmissionValidationError, SQLiteRunSubmissionStore

from okcanvas_agent_runtime.verticals.commerce_snapshot_ingress.catalog import CommerceSnapshotAdapterCatalog
from okcanvas_agent_runtime.verticals.commerce_snapshot_ingress.errors import CommerceSnapshotReplayIntegrityError
from okcanvas_agent_runtime.verticals.commerce_snapshot_ingress.http_adapter import ControlledCommerceHTTPAdapter

_IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9._:-]+$")
_AGENT_ID = "store-replenishment-review-agent"
_TERMINAL_STATES = {
    RunSubmissionRecordState.EXECUTION_SUCCEEDED,
    RunSubmissionRecordState.EXECUTION_FAILED,
    RunSubmissionRecordState.EXECUTION_CANCELLED,
}


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class GovernedCommerceSnapshotIngressService:
    """Acquire one source snapshot before creating the existing governed preflight."""

    def __init__(
        self,
        *,
        project_root: str,
        boundary: RunSubmissionBoundaryService,
        store: SQLiteRunSubmissionStore,
        environment: Mapping[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._catalog = CommerceSnapshotAdapterCatalog(project_root)
        self._boundary = boundary
        self._store = store
        self._environment = environment
        self._transport = transport
        self._locks: dict[str, tuple[asyncio.Lock, int]] = {}
        self._locks_guard = asyncio.Lock()

    async def preflight(
        self,
        *,
        authority_scope: str,
        source_adapter_id: str,
        snapshot_key: str,
        model: str | None,
        idempotency_key: str,
    ) -> RunSubmissionDecision:
        if authority_scope != self._boundary.policy.authority_scope:
            raise RunSubmissionAuthorityError(
                "Local operations read authority does not grant Run submission authority"
            )
        normalized_model = model.strip() if model and model.strip() else None
        if not normalized_model:
            raise RunSubmissionValidationError(
                "A concrete model must be selected before snapshot acquisition"
            )
        policy = self._boundary.policy
        if not (
            policy.idempotency_key_min_length
            <= len(idempotency_key)
            <= policy.idempotency_key_max_length
        ) or not _IDEMPOTENCY_RE.fullmatch(idempotency_key):
            raise RunSubmissionValidationError(
                "Idempotency key has invalid length or characters"
            )
        definition = self._catalog.resolve(source_adapter_id)
        adapter = ControlledCommerceHTTPAdapter(
            definition,
            environment=self._environment,
            transport=self._transport,
        )
        request_sha = adapter.source_request_sha256(snapshot_key)
        idempotency_sha = _sha256_text(idempotency_key)
        lock = await self._retain_lock(idempotency_sha)
        try:
            async with lock:
                existing = self._store.find_by_idempotency_hash(idempotency_sha)
                if existing is not None:
                    self._validate_replay(
                        existing,
                        definition_id=definition.adapter_id,
                        definition_version=definition.version,
                        definition_sha256=definition.definition_sha256,
                        request_sha256=request_sha,
                        model=normalized_model,
                    )
                    return existing
                acquisition = await adapter.acquire(snapshot_key)
                return self._boundary.preflight(
                    authority_scope=authority_scope,
                    agent_definition_id=_AGENT_ID,
                    request=acquisition.canonical_request,
                    model=normalized_model,
                    idempotency_key=idempotency_key,
                    source_binding=acquisition.source_binding,
                )
        finally:
            await self._release_lock(idempotency_sha)

    async def _retain_lock(self, digest: str) -> asyncio.Lock:
        async with self._locks_guard:
            current = self._locks.get(digest)
            if current is None:
                lock = asyncio.Lock()
                self._locks[digest] = (lock, 1)
                return lock
            lock, users = current
            self._locks[digest] = (lock, users + 1)
            return lock

    async def _release_lock(self, digest: str) -> None:
        async with self._locks_guard:
            current = self._locks.get(digest)
            if current is None:
                return
            lock, users = current
            if users <= 1:
                self._locks.pop(digest, None)
            else:
                self._locks[digest] = (lock, users - 1)

    @staticmethod
    def _validate_replay(
        existing: RunSubmissionDecision,
        *,
        definition_id: str,
        definition_version: str,
        definition_sha256: str,
        request_sha256: str,
        model: str,
    ) -> None:
        expected = (
            _AGENT_ID,
            model,
            definition_id,
            definition_version,
            definition_sha256,
            request_sha256,
        )
        actual = (
            existing.agent_definition_id,
            existing.model,
            existing.source_adapter_id,
            existing.source_adapter_version,
            existing.source_adapter_definition_sha256,
            existing.source_request_sha256,
        )
        if actual != expected:
            raise RunSubmissionIdempotencyConflict(
                "Idempotency key was already used for a different commerce snapshot request"
            )
        if (
            not existing.protected_payload_persisted
            and existing.payload_retention_state is not ProtectedPayloadRetentionState.DELETED
            and existing.state not in _TERMINAL_STATES
        ):
            raise CommerceSnapshotReplayIntegrityError(
                "Existing commerce snapshot preflight lost its protected payload"
            )
