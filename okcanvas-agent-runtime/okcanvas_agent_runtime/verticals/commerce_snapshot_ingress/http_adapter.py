from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlsplit

import httpx
from pydantic import ValidationError

from okcanvas_agent_runtime.verticals.store_replenishment import MAX_INVENTORY_UNIT_VALUE, StoreReplenishmentInput
from okcanvas_agent_runtime.application.submissions import RunSubmissionSourceBinding

from okcanvas_agent_runtime.verticals.commerce_snapshot_ingress.errors import CommerceSnapshotAuthenticationError, CommerceSnapshotConfigurationError, CommerceSnapshotIdentityMismatchError, CommerceSnapshotRequestError, CommerceSnapshotResponseError, CommerceSnapshotTooLargeError, CommerceSnapshotUnavailableError, CommerceSnapshotValidationError
from okcanvas_agent_runtime.verticals.commerce_snapshot_ingress.models import CommerceSnapshotAcquisition, CommerceSnapshotAdapterDefinition

_SNAPSHOT_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")

_MAX_INVENTORY_INTEGER_DIGITS = len(str(MAX_INVENTORY_UNIT_VALUE))


def _bounded_json_int(raw: str) -> int:
    digits = raw[1:] if raw.startswith("-") else raw
    if len(digits) > _MAX_INVENTORY_INTEGER_DIGITS:
        raise ValueError("Commerce snapshot integer literal exceeded the digit limit")
    return int(raw)

class _DuplicateJSONKey(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJSONKey(key)
        result[key] = value
    return result


class ControlledCommerceHTTPAdapter:
    """Perform one bounded, read-only, loopback JSON snapshot acquisition."""

    def __init__(
        self,
        definition: CommerceSnapshotAdapterDefinition,
        *,
        environment: Mapping[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.definition = definition
        self._environment = environment if environment is not None else os.environ
        self._transport = transport

    def source_request_sha256(self, snapshot_key: str) -> str:
        normalized = self._normalize_snapshot_key(snapshot_key)
        return _sha256_text(_canonical_json({"snapshot_key": normalized}))

    async def acquire(self, snapshot_key: str) -> CommerceSnapshotAcquisition:
        normalized_key = self._normalize_snapshot_key(snapshot_key)
        base_url, credential = self._resolve_configuration()
        request_sha = self.source_request_sha256(normalized_key)
        path = self.definition.path_template.replace(
            "{snapshot_key}", quote(normalized_key, safe="-._:")
        )
        url = f"{base_url}{path}"
        timeout = httpx.Timeout(
            connect=self.definition.connect_timeout_seconds,
            read=self.definition.read_timeout_seconds,
            write=self.definition.connect_timeout_seconds,
            pool=self.definition.connect_timeout_seconds,
        )
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=timeout,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                async with client.stream(
                    "GET",
                    url,
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Bearer {credential}",
                    },
                ) as response:
                    if response.status_code in {401, 403}:
                        raise CommerceSnapshotAuthenticationError(
                            "Commerce snapshot source rejected the configured credential"
                        )
                    if response.status_code != 200:
                        raise CommerceSnapshotResponseError(
                            f"Commerce snapshot source returned HTTP {response.status_code}"
                        )
                    content_type = response.headers.get("content-type", "")
                    if content_type.split(";", 1)[0].strip().lower() != "application/json":
                        raise CommerceSnapshotResponseError(
                            "Commerce snapshot source did not return application/json"
                        )
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > self.definition.max_response_bytes:
                            raise CommerceSnapshotTooLargeError(
                                "Commerce snapshot source response exceeded the byte limit"
                            )
        except CommerceSnapshotResponseError:
            raise
        except httpx.HTTPError as exc:
            raise CommerceSnapshotUnavailableError(
                "Commerce snapshot source could not be read"
            ) from exc

        if not body:
            raise CommerceSnapshotValidationError("Commerce snapshot response was empty")
        try:
            decoded = bytes(body).decode("utf-8")
            payload = json.loads(
                decoded,
                object_pairs_hook=_reject_duplicate_keys,
                parse_int=_bounded_json_int,
            )
        except (UnicodeDecodeError, ValueError) as exc:
            raise CommerceSnapshotValidationError(
                "Commerce snapshot response is not unambiguous UTF-8 JSON"
            ) from exc
        try:
            snapshot = StoreReplenishmentInput.model_validate(payload)
        except ValidationError as exc:
            raise CommerceSnapshotValidationError(
                "Commerce snapshot response does not match StoreReplenishmentInput"
            ) from exc
        if snapshot.snapshot_id != normalized_key:
            raise CommerceSnapshotIdentityMismatchError(
                "Commerce snapshot identity did not match the requested snapshot key"
            )
        if len(snapshot.items) > self.definition.max_items:
            raise CommerceSnapshotValidationError(
                "Commerce snapshot response exceeded the item-count limit"
            )
        canonical = _canonical_json(snapshot.model_dump(mode="json"))
        snapshot_sha = _sha256_text(canonical)
        return CommerceSnapshotAcquisition(
            canonical_request=canonical,
            source_binding=RunSubmissionSourceBinding(
                adapter_id=self.definition.adapter_id,
                adapter_version=self.definition.version,
                adapter_definition_sha256=self.definition.definition_sha256,
                source_request_sha256=request_sha,
                source_snapshot_sha256=snapshot_sha,
                acquired_at=_utc_now(),
            ),
        )

    @staticmethod
    def _normalize_snapshot_key(snapshot_key: str) -> str:
        normalized = snapshot_key.strip()
        if not _SNAPSHOT_KEY_RE.fullmatch(normalized):
            raise CommerceSnapshotRequestError("Snapshot key has invalid length or characters")
        return normalized

    def _resolve_configuration(self) -> tuple[str, str]:
        raw_base_url = self._environment.get(self.definition.base_url_env, "").strip()
        credential = self._environment.get(self.definition.credential_env, "").strip()
        if not raw_base_url or not credential:
            raise CommerceSnapshotConfigurationError(
                "Commerce snapshot source URL and credential must be configured together"
            )
        if len(credential) > 4096 or "\r" in credential or "\n" in credential:
            raise CommerceSnapshotConfigurationError(
                "Commerce snapshot source credential is invalid"
            )
        parsed = urlsplit(raw_base_url)
        if (
            parsed.scheme != "http"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
            or parsed.hostname is None
            or parsed.port is None
        ):
            raise CommerceSnapshotConfigurationError(
                "Commerce snapshot source URL must be an explicit loopback HTTP origin"
            )
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError as exc:
            raise CommerceSnapshotConfigurationError(
                "Commerce snapshot source host must be a literal loopback IP address"
            ) from exc
        if self.definition.loopback_only and not address.is_loopback:
            raise CommerceSnapshotConfigurationError(
                "Commerce snapshot source must use a loopback IP address"
            )
        return raw_base_url.rstrip("/"), credential
