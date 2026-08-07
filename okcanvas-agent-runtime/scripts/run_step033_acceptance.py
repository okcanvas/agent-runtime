from __future__ import annotations

import argparse
import asyncio
import base64
import json
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import EXPECTED_OPENAI_AGENTS_VERSION, RuntimeSettings
from okcanvas_agent_runtime.core.contracts import CodingAgentResult
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog, GenericAgentExecutionService
from okcanvas_agent_runtime.application.execution import output_registry
from okcanvas_agent_runtime.application.execution.output_registry import OutputContractRuntime
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.adapters.storage.protected_payload import (
    EncryptedFileProtectedPayloadStore,
    ProtectedPayloadKey,
)
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
from okcanvas_agent_runtime.application.submissions import (
    GovernedExecutionLifecycleService,
    GovernedLifecyclePolicyCatalog,
    GovernedReadOnlyRunSubmissionService,
    RunSubmissionBoundaryService,
    RunSubmissionIdempotencyConflict,
    RunSubmissionIntegrityError,
    SQLiteRunSubmissionStore,
)
from okcanvas_agent_runtime.application.approvals import (
    EncryptedRunStateStore,
    GovernedLocalToolApprovalService,
    SQLiteToolApprovalStore,
    ToolApprovalIntegrityError,
)

KEY_TEXT = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")


class NeverGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, **_kwargs):
        self.calls += 1
        raise AssertionError("model gateway must not be called")


class NeverToolGateway:
    def __init__(self) -> None:
        self.prepare_calls = 0
        self.resume_calls = 0

    async def prepare(self, **_kwargs):
        self.prepare_calls += 1
        raise AssertionError("Tool gateway must not be called")

    async def resume(self, **_kwargs):
        self.resume_calls += 1
        raise AssertionError("Tool gateway must not be called")


class CapturingScheduler:
    def __init__(self) -> None:
        self.calls = 0

    async def schedule_prepared(self, *, prepared, settings):
        self.calls += 1
        return object()


def _copy_project(target: Path) -> Path:
    project = target / "project"
    shutil.copytree(ROOT / "specs", project / "specs")
    return project


def _services(root: Path, project: Path):
    database = root / "product.sqlite3"
    product = SQLiteProductStore(database)
    product.initialize()
    submissions = SQLiteRunSubmissionStore(database)
    submissions.initialize()
    payloads = EncryptedFileProtectedPayloadStore(
        root / "payloads", ProtectedPayloadKey.from_text(KEY_TEXT)
    )
    payloads.initialize()
    gateway = NeverGateway()
    execution = GenericAgentExecutionService(
        runtime_bindings=AgentRuntimeBindingCatalog(project),
        definitions=AgentDefinitionCatalog(project),
        store=product,
        gateway=gateway,
        artifact_root=root / "artifacts",
    )
    scheduler = CapturingScheduler()
    boundary = RunSubmissionBoundaryService(
        runtime_bindings=AgentRuntimeBindingCatalog(str(project)),
        project_root=str(project),
        store=submissions,
        protected_payload_store=payloads,
    )
    governed = GovernedReadOnlyRunSubmissionService(
        runtime_bindings=AgentRuntimeBindingCatalog(str(project)),
        project_root=str(project),
        store=submissions,
        protected_payload_store=payloads,
        execution_service=execution,
        scheduler=scheduler,
    )
    return database, product, submissions, payloads, boundary, governed, gateway, scheduler


def _product_counts(product: SQLiteProductStore) -> dict[str, int]:
    tasks, task_count = product.list_tasks(limit=100)
    runs, run_count = product.list_runs(limit=100)
    return {"tasks": task_count, "runs": run_count, "task_rows": len(tasks), "run_rows": len(runs)}


def _table_count(database: Path, table: str) -> int:
    connection = sqlite3.connect(database)
    try:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        connection.close()


def run_acceptance(output: Path) -> int:
    references_before = {
        item.reference_id: item.to_dict()
        for item in ReferenceCatalogService(ROOT).verify_all()
    }
    with AcceptanceWorkspace(step_id="STEP033", output=output) as workspace:
        canonical_catalog = AgentRuntimeBindingCatalog(ROOT)
        canonical_definitions = AgentDefinitionCatalog(ROOT)
        coding_binding = canonical_catalog.resolve(canonical_definitions.resolve("coding-agent"))
        mcp_binding = canonical_catalog.resolve(
            canonical_definitions.resolve("reference-research-agent")
        )
        tool_binding = canonical_catalog.resolve(
            canonical_definitions.resolve("local-text-metrics-agent")
        )

        # Output-contract Runtime drift.
        output_root = workspace.scratch_dir / "output-drift"
        output_project = _copy_project(output_root)
        (
            output_db,
            output_product,
            output_submissions,
            output_payloads,
            output_boundary,
            output_governed,
            output_gateway,
            output_scheduler,
        ) = _services(output_root / "state", output_project)
        output_decision = output_boundary.preflight(
            authority_scope="LOCAL_RUN_SUBMITTER",
            agent_definition_id="coding-agent",
            request="STEP033 bind output Runtime behavior",
            model="acceptance-model",
            idempotency_key="step033-output-runtime-drift-0001",
        )
        protected = output_payloads.read(
            output_decision.protected_payload_ref or "",
            expected_file_sha256=output_decision.protected_payload_sha256 or "",
            expected_byte_length=output_decision.protected_payload_byte_length or 0,
        )
        original_contract = output_registry._OUTPUT_CONTRACTS["CodingAgentResult"]
        output_registry._OUTPUT_CONTRACTS["CodingAgentResult"] = OutputContractRuntime(
            contract_name="CodingAgentResult",
            output_type=CodingAgentResult,
            runtime_version="1.0.1",
            implementation_id="step033-output-runtime-drift-fixture",
        )
        replay_conflict = None
        confirmation_failure = None
        try:
            try:
                output_boundary.preflight(
                    authority_scope="LOCAL_RUN_SUBMITTER",
                    agent_definition_id="coding-agent",
                    request="STEP033 bind output Runtime behavior",
                    model="acceptance-model",
                    idempotency_key="step033-output-runtime-drift-0001",
                )
            except Exception as exc:  # evidence records exact safe type only
                replay_conflict = type(exc).__name__
            try:
                asyncio.run(
                    output_governed.confirm_and_schedule(
                        submission_id=output_decision.submission_id,
                        confirmation=output_decision.confirmation_challenge or "",
                        settings=RuntimeSettings(
                            model="acceptance-model", api_key="redacted-secret"
                        ),
                    )
                )
            except Exception as exc:
                confirmation_failure = type(exc).__name__
        finally:
            output_registry._OUTPUT_CONTRACTS["CodingAgentResult"] = original_contract
        output_counts = _product_counts(output_product)

        # MCP definition drift.
        mcp_root = workspace.scratch_dir / "mcp-drift"
        mcp_project = _copy_project(mcp_root)
        (
            _mcp_db,
            mcp_product,
            _mcp_submissions,
            _mcp_payloads,
            mcp_boundary,
            mcp_governed,
            mcp_gateway,
            mcp_scheduler,
        ) = _services(mcp_root / "state", mcp_project)
        mcp_decision = mcp_boundary.preflight(
            authority_scope="LOCAL_RUN_SUBMITTER",
            agent_definition_id="reference-research-agent",
            request="STEP033 bind MCP Runtime behavior",
            model="acceptance-model",
            idempotency_key="step033-mcp-runtime-drift-0001",
        )
        server_path = (
            mcp_project
            / "specs"
            / "mcp"
            / "servers"
            / "reference-catalog"
            / "server.json"
        )
        server_payload = json.loads(server_path.read_text(encoding="utf-8"))
        server_payload["max_result_chars"] = int(server_payload["max_result_chars"]) - 1
        server_path.write_text(
            json.dumps(server_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        mcp_failure = None
        try:
            asyncio.run(
                mcp_governed.confirm_and_schedule(
                    submission_id=mcp_decision.submission_id,
                    confirmation=mcp_decision.confirmation_challenge or "",
                    settings=RuntimeSettings(
                        model="acceptance-model", api_key="redacted-secret"
                    ),
                )
            )
        except Exception as exc:
            mcp_failure = type(exc).__name__
        mcp_counts = _product_counts(mcp_product)

        # Local Tool policy drift.
        tool_root = workspace.scratch_dir / "tool-drift"
        tool_project = _copy_project(tool_root)
        (
            tool_db,
            tool_product,
            tool_submissions,
            tool_payloads,
            tool_boundary,
            _tool_governed,
            tool_model_gateway,
            _tool_scheduler,
        ) = _services(tool_root / "state", tool_project)
        tool_decision = tool_boundary.preflight(
            authority_scope="LOCAL_RUN_SUBMITTER",
            agent_definition_id="local-text-metrics-agent",
            request="STEP033 bind local Tool Runtime behavior",
            model="acceptance-model",
            idempotency_key="step033-local-tool-runtime-drift-0001",
        )
        tool_policy_path = (
            tool_project / "specs" / "tools" / "local-text-metrics" / "policy.yaml"
        )
        tool_policy_path.write_text(
            tool_policy_path.read_text(encoding="utf-8") + "\n# step033 drift fixture\n",
            encoding="utf-8",
        )
        lifecycle_policy = GovernedLifecyclePolicyCatalog(tool_project).resolve()
        lifecycle = GovernedExecutionLifecycleService(
            submission_store=tool_submissions,
            product_store=tool_product,
            payload_store=tool_payloads,
            policy=lifecycle_policy,
        )
        state_store = EncryptedRunStateStore(
            tool_root / "run-states", tool_payloads.key
        )
        state_store.initialize()
        approval_store = SQLiteToolApprovalStore(tool_db)
        approval_store.initialize()
        tool_gateway = NeverToolGateway()
        tool_service = GovernedLocalToolApprovalService(
            runtime_bindings=AgentRuntimeBindingCatalog(tool_project),
            project_root=tool_project,
            submission_store=tool_submissions,
            product_store=tool_product,
            payload_store=tool_payloads,
            run_state_store=state_store,
            approval_store=approval_store,
            artifact_root=tool_root / "artifacts",
            lifecycle_service=lifecycle,
            gateway=tool_gateway,
        )
        tool_failure = None
        try:
            asyncio.run(
                tool_service.prepare(
                    submission_id=tool_decision.submission_id,
                    settings=RuntimeSettings(
                        model="acceptance-model", api_key="redacted-secret"
                    ),
                )
            )
        except Exception as exc:
            tool_failure = type(exc).__name__
        tool_counts = _product_counts(tool_product)
        approval_count = _table_count(tool_db, "governed_tool_approval")

        references_after = {
            item.reference_id: item.to_dict()
            for item in ReferenceCatalogService(ROOT).verify_all()
        }
        checks = {
            "three_current_execution_paths_bound": len(
                {
                    coding_binding.runtime_binding_sha256,
                    mcp_binding.runtime_binding_sha256,
                    tool_binding.runtime_binding_sha256,
                }
            )
            == 3,
            "sdk_version_bound": coding_binding.sdk_version
            == EXPECTED_OPENAI_AGENTS_VERSION,
            "output_contract_runtime_bound": len(
                coding_binding.output_contract_runtime_sha256
            )
            == 64,
            "mcp_definition_and_module_bound": len(mcp_binding.mcp_servers) == 1
            and len(mcp_binding.mcp_servers[0]["definition_sha256"]) == 64
            and len(mcp_binding.mcp_servers[0]["module_sha256"]) == 64,
            "local_tool_policy_and_implementation_bound": len(tool_binding.local_tools)
            == 1
            and len(tool_binding.local_tools[0]["policy_sha256"]) == 64
            and len(tool_binding.local_tools[0]["implementation_sha256"]) == 64,
            "runtime_binding_persisted_in_ledger": output_submissions.get(
                output_decision.submission_id
            ).runtime_binding_sha256
            == output_decision.runtime_binding_sha256,
            "runtime_binding_persisted_in_protected_payload": protected.runtime_binding_sha256
            == output_decision.runtime_binding_sha256,
            "runtime_binding_in_confirmation_fingerprint": output_decision.runtime_binding_sha256
            in json.dumps(output_decision.to_public_dict(), sort_keys=True),
            "output_runtime_drift_conflicts_idempotent_replay": replay_conflict
            == RunSubmissionIdempotencyConflict.__name__,
            "output_runtime_drift_blocks_confirmation": confirmation_failure
            == RunSubmissionIntegrityError.__name__,
            "output_runtime_drift_created_no_product_state": output_counts["tasks"] == 0
            and output_counts["runs"] == 0,
            "output_runtime_drift_called_no_scheduler_or_model": output_scheduler.calls == 0
            and output_gateway.calls == 0,
            "mcp_drift_blocks_confirmation": mcp_failure
            == RunSubmissionIntegrityError.__name__,
            "mcp_drift_created_no_product_state": mcp_counts["tasks"] == 0
            and mcp_counts["runs"] == 0,
            "mcp_drift_called_no_scheduler_or_model": mcp_scheduler.calls == 0
            and mcp_gateway.calls == 0,
            "local_tool_policy_drift_blocks_prepare": tool_failure
            == ToolApprovalIntegrityError.__name__,
            "local_tool_drift_created_no_product_or_approval_state": tool_counts["tasks"]
            == 0
            and tool_counts["runs"] == 0
            and approval_count == 0,
            "local_tool_drift_called_no_gateway_or_model": tool_gateway.prepare_calls == 0
            and tool_gateway.resume_calls == 0
            and tool_model_gateway.calls == 0,
            "runtime_binding_sha_is_non_secret": KEY_TEXT not in json.dumps(
                {
                    "coding": coding_binding.to_fingerprint_dict(),
                    "mcp": mcp_binding.to_fingerprint_dict(),
                    "tool": tool_binding.to_fingerprint_dict(),
                },
                sort_keys=True,
            ),
            "references_unchanged": references_before == references_after,
        }
        payload = {
            "schema_version": "okcanvas-step033-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "binding_count": 3,
            "bindings": {
                "coding": coding_binding.to_fingerprint_dict(),
                "reference_research": mcp_binding.to_fingerprint_dict(),
                "local_text_metrics": tool_binding.to_fingerprint_dict(),
            },
            "output_runtime_drift": {
                "replay_failure": replay_conflict,
                "confirmation_failure": confirmation_failure,
                "product_counts": output_counts,
                "scheduler_calls": output_scheduler.calls,
                "gateway_calls": output_gateway.calls,
            },
            "mcp_drift": {
                "confirmation_failure": mcp_failure,
                "product_counts": mcp_counts,
                "scheduler_calls": mcp_scheduler.calls,
                "gateway_calls": mcp_gateway.calls,
            },
            "local_tool_drift": {
                "prepare_failure": tool_failure,
                "product_counts": tool_counts,
                "approval_count": approval_count,
                "tool_gateway_prepare_calls": tool_gateway.prepare_calls,
                "tool_gateway_resume_calls": tool_gateway.resume_calls,
                "model_gateway_calls": tool_model_gateway.calls,
            },
        }
        payload = workspace.finalize(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP033_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
