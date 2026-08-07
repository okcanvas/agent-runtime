from __future__ import annotations

from dataclasses import dataclass

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_NAME, PROJECT_VERSION
from okcanvas_agent_runtime.application.evaluation import EvaluationCatalog, EvaluationSuiteCatalog
from okcanvas_agent_runtime.agent.mcp.definitions import MCPServerCatalog
from okcanvas_agent_runtime.application.approvals.models import ToolApprovalState
from okcanvas_agent_runtime.application.operations.ports import (
    OperationsEvaluationStorePort,
    OperationsProductStorePort,
    OperationsReferenceCatalogPort,
    OperationsToolApprovalStorePort,
)


@dataclass
class OperationsSnapshotService:
    """Build a bounded, read-only operations snapshot from product-owned stores and catalogs."""

    product_store: OperationsProductStorePort
    evaluation_store: OperationsEvaluationStorePort
    tool_approval_store: OperationsToolApprovalStorePort
    agent_catalog: AgentDefinitionCatalog
    evaluation_catalog: EvaluationCatalog
    evaluation_suite_catalog: EvaluationSuiteCatalog
    mcp_catalog: MCPServerCatalog
    reference_catalog: OperationsReferenceCatalogPort

    def __post_init__(self) -> None:
        self._reference_verifications = self.reference_catalog.verify_all()

    def snapshot(self, *, refresh_references: bool = False) -> dict[str, object]:
        tasks, task_total = self.product_store.list_tasks(limit=1)
        del tasks
        runs, run_total = self.product_store.list_runs(limit=10)
        evaluation_stats = self.evaluation_store.statistics()
        approval_states = self.tool_approval_store.state_counts()
        approval_total = sum(approval_states.values())
        references = (
            self.reference_catalog.verify_all()
            if refresh_references
            else self._reference_verifications
        )
        if refresh_references:
            self._reference_verifications = references
        agents = self.agent_catalog.list_definitions()
        cases = self.evaluation_catalog.list_cases()
        suites = self.evaluation_suite_catalog.list_suites()
        mcp_servers = self.mcp_catalog.list_servers()
        return {
            "schema_version": "okcanvas-operations-summary-v1",
            "runtime": {
                "project": PROJECT_NAME,
                "version": PROJECT_VERSION,
                "step": CURRENT_STEP,
                "mode": "local-admin-only",
                "console_mode": "read-only",
            },
            "product": {
                "task_total": task_total,
                "task_status_counts": self.product_store.task_status_counts(),
                "run_total": run_total,
                "run_status_counts": self.product_store.run_status_counts(),
                "artifact_total": self.product_store.artifact_count(),
            },
            "catalog": {
                "agent_definition_total": len(agents),
                "evaluation_case_total": len(cases),
                "evaluation_suite_total": len(suites),
                "mcp_server_total": len(mcp_servers),
                "mcp_servers": [
                    {
                        "server_id": item.server_id,
                        "version": item.version,
                        "name": item.name,
                        "read_only": item.read_only,
                        "allowed_tools": list(item.allowed_tools),
                    }
                    for item in mcp_servers
                ],
            },
            "evaluation": evaluation_stats,
            "approvals": {
                "approval_total": approval_total,
                "pending_total": approval_states[ToolApprovalState.PENDING.value],
                "approval_states": approval_states,
            },
            "references": {
                "total": len(references),
                "verified": sum(1 for item in references if item.verified),
                "items": [item.to_dict() for item in references],
            },
            "recent_runs": runs,
        }
