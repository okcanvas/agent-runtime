from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from okcanvas_agent_runtime.application.scenarios.models import ScenarioActionMode, WalkingSkeletonScenario


class WalkingSkeletonCatalogError(ValueError):
    code = "WALKING_SKELETON_CATALOG_INVALID"


class WalkingSkeletonScenarioCatalog:
    SCHEMA_VERSION = "okcanvas-walking-skeleton-scenario-catalog-v1"
    REQUIRED_SCENARIOS = (
        "tool-free-structured",
        "read-only-function-tool",
        "approval-function-tool",
        "read-only-mcp",
        "native-sdk-streaming",
        "native-handoff",
        "agent-as-tool",
        "sqlite-session-two-turn",
        "native-guardrail-rejection",
        "artifact-recorded-evaluation",
    )

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).expanduser().resolve()
        self.path = self.project_root / "specs" / "runtime" / "walking-skeleton-scenarios.json"
        self._scenarios, self.catalog_id, self.version, self.catalog_sha256 = self._load()

    def _load(self) -> tuple[tuple[WalkingSkeletonScenario, ...], str, str, str]:
        try:
            resolved = self.path.resolve(strict=True)
        except OSError as exc:
            raise WalkingSkeletonCatalogError("Walking skeleton scenario catalog is missing") from exc
        expected_parent = (self.project_root / "specs" / "runtime").resolve()
        if self.path.is_symlink() or resolved.parent != expected_parent or not resolved.is_file():
            raise WalkingSkeletonCatalogError("Walking skeleton scenario catalog path is invalid")
        raw = resolved.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WalkingSkeletonCatalogError("Walking skeleton scenario catalog is not valid JSON") from exc
        if not isinstance(payload, dict) or set(payload) != {"schema_version", "catalog_id", "version", "scenarios"}:
            raise WalkingSkeletonCatalogError("Walking skeleton scenario catalog fields are invalid")
        if payload["schema_version"] != self.SCHEMA_VERSION:
            raise WalkingSkeletonCatalogError("Walking skeleton scenario catalog schema is unsupported")
        catalog_id = self._identifier(payload["catalog_id"], "catalog_id")
        version = self._version(payload["version"])
        rows = payload["scenarios"]
        if not isinstance(rows, list) or len(rows) != len(self.REQUIRED_SCENARIOS):
            raise WalkingSkeletonCatalogError("Walking skeleton scenario count is invalid")
        scenarios = tuple(self._parse(row) for row in rows)
        ids = tuple(item.scenario_id for item in scenarios)
        if ids != self.REQUIRED_SCENARIOS or len(set(ids)) != len(ids):
            raise WalkingSkeletonCatalogError("Walking skeleton scenario order or identity is invalid")
        return scenarios, catalog_id, version, hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _identifier(value: object, field: str) -> str:
        if not isinstance(value, str) or re.fullmatch(r"[a-z][a-z0-9-]{1,95}", value) is None:
            raise WalkingSkeletonCatalogError(f"{field} is invalid")
        return value

    @staticmethod
    def _version(value: object) -> str:
        if not isinstance(value, str) or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value) is None:
            raise WalkingSkeletonCatalogError("version is invalid")
        return value

    @staticmethod
    def _strings(value: object, field: str, *, minimum: int = 1) -> tuple[str, ...]:
        if not isinstance(value, list) or len(value) < minimum or not all(isinstance(item, str) and item for item in value):
            raise WalkingSkeletonCatalogError(f"{field} is invalid")
        result = tuple(value)
        if len(set(result)) != len(result):
            raise WalkingSkeletonCatalogError(f"{field} contains duplicates")
        return result

    def _parse(self, row: object) -> WalkingSkeletonScenario:
        expected = {
            "scenario_id", "title", "summary", "agent_definition_id", "action_mode",
            "request_templates", "evaluation_case_id", "expected_terminal_state",
            "expected_error_code", "requires_session", "requires_approval_operator",
            "capabilities", "invocation_kinds", "workspace_access",
        }
        if not isinstance(row, dict) or set(row) != expected:
            raise WalkingSkeletonCatalogError("Walking skeleton scenario fields are invalid")
        try:
            action = ScenarioActionMode(row["action_mode"])
        except (TypeError, ValueError) as exc:
            raise WalkingSkeletonCatalogError("Walking skeleton action mode is invalid") from exc
        if not isinstance(row["title"], str) or not row["title"].strip():
            raise WalkingSkeletonCatalogError("Walking skeleton title is invalid")
        if not isinstance(row["summary"], str) or not row["summary"].strip():
            raise WalkingSkeletonCatalogError("Walking skeleton summary is invalid")
        if row["expected_terminal_state"] not in {"SUCCEEDED", "FAILED", "INTERRUPTED"}:
            raise WalkingSkeletonCatalogError("Walking skeleton terminal state is invalid")
        if row["workspace_access"] != "none":
            raise WalkingSkeletonCatalogError("P0 walking skeleton scenarios must be workspace-free")
        if not isinstance(row["requires_session"], bool) or not isinstance(row["requires_approval_operator"], bool):
            raise WalkingSkeletonCatalogError("Walking skeleton authority flags are invalid")
        evaluation = row["evaluation_case_id"]
        error_code = row["expected_error_code"]
        if evaluation is not None:
            evaluation = self._identifier(evaluation, "evaluation_case_id")
        if error_code is not None and (not isinstance(error_code, str) or re.fullmatch(r"[A-Z][A-Z0-9_]{2,95}", error_code) is None):
            raise WalkingSkeletonCatalogError("expected_error_code is invalid")
        requests = self._strings(row["request_templates"], "request_templates")
        capabilities = self._strings(row["capabilities"], "capabilities")
        invocation_kinds = self._strings(row["invocation_kinds"], "invocation_kinds")
        if not all(re.fullmatch(r"[A-Z][A-Z0-9_]{1,63}", item) for item in capabilities):
            raise WalkingSkeletonCatalogError("capabilities are invalid")
        if not set(invocation_kinds).issubset({"ROOT", "HANDOFF", "AGENT_AS_TOOL"}):
            raise WalkingSkeletonCatalogError("invocation_kinds are invalid")
        if action is ScenarioActionMode.SESSION_TWO_TURN and not row["requires_session"]:
            raise WalkingSkeletonCatalogError("Session scenario must require a Session")
        if action is not ScenarioActionMode.SESSION_TWO_TURN and row["requires_session"]:
            raise WalkingSkeletonCatalogError("Only the Session scenario may require a Session")
        if action is ScenarioActionMode.PREPARE_APPROVAL and not row["requires_approval_operator"]:
            raise WalkingSkeletonCatalogError("Approval scenario must require the Approval Operator")
        if action is not ScenarioActionMode.PREPARE_APPROVAL and row["requires_approval_operator"]:
            raise WalkingSkeletonCatalogError("Only the approval scenario may require the Approval Operator")
        if action is ScenarioActionMode.EXPECTED_FAILURE and error_code is None:
            raise WalkingSkeletonCatalogError("Expected-failure scenario requires an error code")
        if action is not ScenarioActionMode.EXPECTED_FAILURE and error_code is not None:
            raise WalkingSkeletonCatalogError("Only expected-failure scenario may declare an error code")
        if action is ScenarioActionMode.SESSION_TWO_TURN and len(requests) != 2:
            raise WalkingSkeletonCatalogError("Session scenario must contain exactly two Turn templates")
        if action is not ScenarioActionMode.SESSION_TWO_TURN and len(requests) != 1:
            raise WalkingSkeletonCatalogError("Non-Session scenario must contain one request template")
        return WalkingSkeletonScenario(
            scenario_id=self._identifier(row["scenario_id"], "scenario_id"),
            title=str(row["title"]),
            summary=str(row["summary"]),
            agent_definition_id=self._identifier(row["agent_definition_id"], "agent_definition_id"),
            action_mode=action,
            request_templates=requests,
            evaluation_case_id=evaluation,
            expected_terminal_state=row["expected_terminal_state"],
            expected_error_code=error_code,
            requires_session=row["requires_session"],
            requires_approval_operator=row["requires_approval_operator"],
            capabilities=capabilities,
            invocation_kinds=invocation_kinds,
            workspace_access=row["workspace_access"],
        )

    def list_scenarios(self) -> tuple[WalkingSkeletonScenario, ...]:
        return self._scenarios

    def resolve(self, scenario_id: str) -> WalkingSkeletonScenario:
        for scenario in self._scenarios:
            if scenario.scenario_id == scenario_id:
                return scenario
        raise KeyError(scenario_id)
