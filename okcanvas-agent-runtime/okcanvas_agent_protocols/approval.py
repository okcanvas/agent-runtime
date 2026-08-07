"""Transport-neutral approval confirmation contracts."""
from __future__ import annotations


def decision_confirmation_challenge(*, approval_id: str, run_id: str, decision: str) -> str:
    normalized = str(decision).strip().upper()
    if normalized not in {"APPROVE", "REJECT"}:
        raise ValueError("decision must be APPROVE or REJECT")
    return f"{normalized} {approval_id} {run_id}"
