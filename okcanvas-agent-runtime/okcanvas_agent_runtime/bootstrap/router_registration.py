"""Fail-closed Product-owned FastAPI router registration.

STEP081D owns the final reconciliation between route builders and the composed
FastAPI application.  Normal FastAPI ``include_router`` remains the primary
path.  A bounded direct-registration fallback is used only when the framework
call returns without registering one or more already-constructed APIRoutes.
The final method/path inventory is always verified exactly.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from fastapi import APIRouter, FastAPI


@dataclass(frozen=True)
class RouterRegistrationEvidence:
    owner: str
    expected_route_count: int
    registered_route_count: int
    fallback_applied: bool
    missing_after_include: tuple[tuple[str, str], ...]
    missing_after_reconciliation: tuple[tuple[str, str], ...]
    duplicate_method_paths: tuple[tuple[str, str, int], ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["missing_after_include"] = [
            {"method": method, "path": path} for method, path in self.missing_after_include
        ]
        payload["missing_after_reconciliation"] = [
            {"method": method, "path": path}
            for method, path in self.missing_after_reconciliation
        ]
        payload["duplicate_method_paths"] = [
            {"method": method, "path": path, "count": count}
            for method, path, count in self.duplicate_method_paths
        ]
        return payload


def _route_pairs(routes: Iterable[Any]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for route in routes:
        path = str(getattr(route, "path", ""))
        methods = {
            str(method).upper()
            for method in (getattr(route, "methods", set()) or set())
        } - {"HEAD", "OPTIONS"}
        pairs.extend((method, path) for method in sorted(methods))
    return pairs


def include_router_exact(app: FastAPI, router: APIRouter, *, owner: str) -> RouterRegistrationEvidence:
    """Register a non-empty router and verify its final method/path inventory.

    ``FastAPI.include_router`` is used first.  If it returns without registering
    some of the already-built routes, only the missing route objects are added
    directly to the application's router.  The function then fails closed if
    any expected method/path remains absent or if reconciliation introduces a
    duplicate.
    """

    expected_pairs = _route_pairs(router.routes)
    if not expected_pairs:
        raise RuntimeError(f"{owner} router contains no HTTP routes")
    if len(expected_pairs) != len(set(expected_pairs)):
        raise RuntimeError(f"{owner} router contains duplicate method/path declarations")

    before_pairs = set(_route_pairs(app.routes))
    app.include_router(router)
    after_include_pairs = set(_route_pairs(app.routes))
    missing_after_include = tuple(sorted(set(expected_pairs) - after_include_pairs))

    fallback_applied = False
    if missing_after_include:
        fallback_applied = True
        missing_set = set(missing_after_include)
        for route in router.routes:
            route_pairs = set(_route_pairs((route,)))
            if route_pairs & missing_set:
                app.router.routes.append(route)

    final_pairs_list = _route_pairs(app.routes)
    final_pairs = set(final_pairs_list)
    missing_after_reconciliation = tuple(sorted(set(expected_pairs) - final_pairs))
    counts = Counter(final_pairs_list)
    duplicates = tuple(
        (method, path, count)
        for (method, path), count in sorted(counts.items())
        if count > 1 and (method, path) not in before_pairs
    )
    if missing_after_reconciliation or duplicates:
        raise RuntimeError(
            f"{owner} router registration failed: "
            f"missing={list(missing_after_reconciliation)!r} duplicates={list(duplicates)!r}"
        )

    evidence = RouterRegistrationEvidence(
        owner=owner,
        expected_route_count=len(expected_pairs),
        registered_route_count=len(set(expected_pairs) & final_pairs),
        fallback_applied=fallback_applied,
        missing_after_include=missing_after_include,
        missing_after_reconciliation=missing_after_reconciliation,
        duplicate_method_paths=duplicates,
    )
    existing = list(getattr(app.state, "router_registration_evidence", ()))
    existing.append(evidence.to_dict())
    app.state.router_registration_evidence = tuple(existing)
    return evidence
