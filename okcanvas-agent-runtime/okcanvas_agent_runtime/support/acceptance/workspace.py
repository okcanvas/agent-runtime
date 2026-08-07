from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class AcceptanceWorkspaceError(RuntimeError):
    """Raised when an acceptance workspace cannot complete its lifecycle safely."""


@dataclass(frozen=True)
class ResourceCloseResult:
    name: str
    closed: bool
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "closed": self.closed, "error": self.error}


class AcceptanceWorkspace:
    """Project-owned isolated workspace for deterministic acceptance runs.

    The workspace is deleted only after registered resources have been explicitly closed and
    compact evidence has been copied outside the workspace. Failed runs are preserved and their
    exact path is surfaced for investigation.
    """

    def __init__(
        self,
        *,
        step_id: str,
        output: Path | None = None,
        base_dir: Path | None = None,
        acceptance_id: str | None = None,
        cleanup_attempts: int = 3,
        cleanup_delay_seconds: float = 0.1,
    ) -> None:
        if not step_id or any(ch in step_id for ch in "\\/:"):
            raise ValueError("step_id must be a non-empty filesystem-safe identifier")
        if cleanup_attempts < 1 or cleanup_attempts > 10:
            raise ValueError("cleanup_attempts must be between 1 and 10")
        if cleanup_delay_seconds < 0 or cleanup_delay_seconds > 5:
            raise ValueError("cleanup_delay_seconds must be between 0 and 5")

        self.step_id = step_id
        self.acceptance_id = acceptance_id or self._new_acceptance_id()
        configured_root = os.environ.get("OKCANVAS_ACCEPTANCE_WORK_ROOT")
        root_base = (
            Path(configured_root)
            if configured_root
            else base_dir
            if base_dir is not None
            else Path(tempfile.gettempdir()) / "okcanvas-agent-runtime-acceptance"
        )
        self.root = root_base.resolve() / step_id.casefold() / self.acceptance_id
        self.database_dir = self.root / "databases"
        self.artifact_dir = self.root / "artifacts"
        self.scratch_dir = self.root / "scratch"
        self.evidence_dir = self.root / "evidence"
        self.output = output.resolve() if output is not None else None
        self.cleanup_attempts = cleanup_attempts
        self.cleanup_delay_seconds = cleanup_delay_seconds
        self._closers: list[tuple[str, Callable[[], Any]]] = []
        self._close_results: list[ResourceCloseResult] = []
        self._resources_closed = False
        self._finalized = False
        self._created_at = self._utc_now()

        for path in (
            self.database_dir,
            self.artifact_dir,
            self.scratch_dir,
            self.evidence_dir,
        ):
            path.mkdir(parents=True, exist_ok=False)
        self._write_atomic(
            self.root / "workspace.json",
            {
                "schema_version": "okcanvas-acceptance-workspace-v1",
                "step_id": self.step_id,
                "acceptance_id": self.acceptance_id,
                "created_at": self._created_at,
                "owner": "acceptance-only",
                "product_runtime_state": False,
            },
        )

    @staticmethod
    def _new_acceptance_id() -> str:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        return f"{stamp}-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _write_atomic(path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    def register_closer(self, name: str, closer: Callable[[], Any]) -> None:
        if self._resources_closed:
            raise AcceptanceWorkspaceError("resources are already closed")
        if not name:
            raise ValueError("closer name must not be empty")
        self._closers.append((name, closer))

    def close_resources(self) -> tuple[ResourceCloseResult, ...]:
        if self._resources_closed:
            return tuple(self._close_results)
        for name, closer in reversed(self._closers):
            try:
                closer()
            except Exception as exc:  # noqa: BLE001 - evidence must retain the close failure
                self._close_results.append(
                    ResourceCloseResult(name=name, closed=False, error=f"{type(exc).__name__}: {exc}")
                )
            else:
                self._close_results.append(ResourceCloseResult(name=name, closed=True))
        self._resources_closed = True
        return tuple(self._close_results)

    def _lifecycle_payload(
        self,
        *,
        cleanup_state: str,
        cleanup_attempts_used: int,
        preserved_path: str | None,
        cleanup_error: str | None,
    ) -> dict[str, object]:
        return {
            "schema_version": "okcanvas-acceptance-workspace-lifecycle-v1",
            "acceptance_id": self.acceptance_id,
            "step_id": self.step_id,
            "created_at": self._created_at,
            "completed_at": self._utc_now(),
            "resources_closed": self._resources_closed
            and all(item.closed for item in self._close_results),
            "resource_close_results": [item.to_dict() for item in self._close_results],
            "compact_evidence_exported": self.output is not None,
            "cleanup_state": cleanup_state,
            "cleanup_attempts": cleanup_attempts_used,
            "preserved_path": preserved_path,
            "cleanup_error": cleanup_error,
            "product_runtime_state": False,
        }

    def _remove_tree(self) -> tuple[bool, int, str | None]:
        last_error: str | None = None
        for attempt in range(1, self.cleanup_attempts + 1):
            try:
                shutil.rmtree(self.root, ignore_errors=False)
                return True, attempt, None
            except FileNotFoundError:
                return True, attempt, None
            except Exception as exc:  # noqa: BLE001 - bounded Windows cleanup evidence
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt < self.cleanup_attempts:
                    time.sleep(self.cleanup_delay_seconds)
        return False, self.cleanup_attempts, last_error

    def finalize(self, payload: dict[str, object]) -> dict[str, object]:
        if self._finalized:
            raise AcceptanceWorkspaceError("workspace is already finalized")
        self._finalized = True
        original_state = str(payload.get("state", "FAILED"))
        close_results = self.close_resources()
        close_ok = all(item.closed for item in close_results)
        requested_pass = original_state == "PASSED"

        staged = dict(payload)
        staged["acceptance_workspace"] = self._lifecycle_payload(
            cleanup_state="PENDING" if requested_pass and close_ok else "PRESERVED",
            cleanup_attempts_used=0,
            preserved_path=None if requested_pass and close_ok else str(self.root),
            cleanup_error=None,
        )
        self._write_atomic(self.evidence_dir / "acceptance-summary.json", staged)
        if self.output is not None:
            self._write_atomic(self.output, staged)

        if requested_pass and close_ok:
            removed, attempts, cleanup_error = self._remove_tree()
            if removed:
                final = dict(payload)
                final["acceptance_workspace"] = self._lifecycle_payload(
                    cleanup_state="COMPLETED",
                    cleanup_attempts_used=attempts,
                    preserved_path=None,
                    cleanup_error=None,
                )
            else:
                final = dict(payload)
                final["state_before_workspace_cleanup"] = original_state
                final["state"] = "FAILED"
                final["acceptance_workspace"] = self._lifecycle_payload(
                    cleanup_state="PRESERVED",
                    cleanup_attempts_used=attempts,
                    preserved_path=str(self.root),
                    cleanup_error=cleanup_error,
                )
                print(f"[ERROR] Acceptance workspace preserved: {self.root}", file=sys.stderr)
        else:
            final = dict(payload)
            if not close_ok:
                final["state_before_resource_close"] = original_state
                final["state"] = "FAILED"
            final["acceptance_workspace"] = self._lifecycle_payload(
                cleanup_state="PRESERVED",
                cleanup_attempts_used=0,
                preserved_path=str(self.root),
                cleanup_error="one or more registered resources failed to close" if not close_ok else None,
            )
            print(f"[INFO] Acceptance workspace preserved: {self.root}", file=sys.stderr)

        if self.output is not None:
            self._write_atomic(self.output, final)
        elif self.root.exists():
            self._write_atomic(self.evidence_dir / "acceptance-summary.json", final)
        return final

    def preserve_exception(self, exc: BaseException) -> None:
        if self._finalized:
            return
        self._finalized = True
        self.close_resources()
        payload: dict[str, object] = {
            "schema_version": "okcanvas-acceptance-exception-v1",
            "state": "FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "acceptance_workspace": self._lifecycle_payload(
                cleanup_state="PRESERVED",
                cleanup_attempts_used=0,
                preserved_path=str(self.root),
                cleanup_error=None,
            ),
        }
        self._write_atomic(self.evidence_dir / "acceptance-summary.json", payload)
        if self.output is not None:
            self._write_atomic(self.output, payload)
        print(f"[ERROR] Acceptance workspace preserved: {self.root}", file=sys.stderr)

    def __enter__(self) -> AcceptanceWorkspace:
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        _ = (exc_type, traceback)
        if exc is not None:
            self.preserve_exception(exc)
        elif not self._finalized:
            self.close_resources()
        return False
