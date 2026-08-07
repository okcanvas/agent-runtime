from __future__ import annotations

import time
from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True)
class MCPHealthState:
    server_id: str
    state: str
    consecutive_failures: int
    opened_until_monotonic: float | None


class MCPPassiveHealthRegistry:
    """Process-local passive circuit state; no background probe and no credential use."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._states: dict[str, MCPHealthState] = {}

    def require_available(self, server_id: str) -> None:
        with self._lock:
            state = self._states.get(server_id)
            if state and state.state == "OPEN" and state.opened_until_monotonic and time.monotonic() < state.opened_until_monotonic:
                raise RuntimeError(f"Remote MCP circuit is open: {server_id}")
            if state and state.state == "OPEN":
                self._states[server_id] = MCPHealthState(server_id, "HALF_OPEN", state.consecutive_failures, None)

    def record_success(self, server_id: str) -> None:
        with self._lock:
            self._states[server_id] = MCPHealthState(server_id, "CLOSED", 0, None)

    def record_failure(self, server_id: str, *, threshold: int, reset_seconds: float) -> None:
        with self._lock:
            current = self._states.get(server_id)
            failures = (current.consecutive_failures if current else 0) + 1
            if failures >= threshold:
                self._states[server_id] = MCPHealthState(server_id, "OPEN", failures, time.monotonic() + reset_seconds)
            else:
                self._states[server_id] = MCPHealthState(server_id, "CLOSED", failures, None)

    def snapshot(self) -> tuple[MCPHealthState, ...]:
        with self._lock:
            return tuple(self._states[key] for key in sorted(self._states))
