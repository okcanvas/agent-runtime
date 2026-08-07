from __future__ import annotations

from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog

import argparse
import base64
import json
import shutil
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
from okcanvas_agent_runtime.adapters.storage.protected_payload import (
    EncryptedFileProtectedPayloadStore,
    ProtectedPayloadKey,
)
from okcanvas_agent_runtime.application.submissions import (
    RunSubmissionAuthorityError,
    RunSubmissionBoundaryService,
    RunSubmissionExecutionMode,
    RunSubmissionIdempotencyConflict,
    SQLiteRunSubmissionStore,
)

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step017-acceptance-admin-key"
HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
RAW_REQUEST = "STEP017 acceptance raw input must not be persisted"
IDEMPOTENCY_KEY = "step017-acceptance-idempotency-0001"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")


class ExplodingGateway:
    async def run(self, **kwargs):
        raise AssertionError("Direct Run execution must remain disabled")


def _counts(database: Path) -> tuple[int, int, int]:
    connection = sqlite3.connect(database)
    try:
        task_count = int(connection.execute("SELECT COUNT(*) FROM task").fetchone()[0])
        run_count = int(connection.execute("SELECT COUNT(*) FROM run").fetchone()[0])
        submission_count = int(
            connection.execute("SELECT COUNT(*) FROM run_submission_preflight").fetchone()[0]
        )
        return task_count, run_count, submission_count
    finally:
        connection.close()


def run_acceptance(output: Path) -> int:
    references_before = {
        item.reference_id: item.to_dict()
        for item in ReferenceCatalogService(ROOT).verify_all()
    }
    with AcceptanceWorkspace(step_id="STEP017", output=output) as workspace:
        product_db = workspace.database_dir / "product.sqlite3"
        app = create_app(
            project_root=ROOT,
            product_db=product_db,
            artifact_root=workspace.artifact_dir,
            evaluation_db=workspace.database_dir / "evaluation.sqlite3",
            admin_key=ADMIN_KEY,
            gateway=ExplodingGateway(),
        )
        submission_store = SQLiteRunSubmissionStore(product_db)
        submission_store.initialize()
        payload_store = EncryptedFileProtectedPayloadStore(
            workspace.scratch_dir / "protected", ProtectedPayloadKey.from_text(PAYLOAD_KEY)
        )
        service = RunSubmissionBoundaryService(
            runtime_bindings=AgentRuntimeBindingCatalog(str(ROOT)),
            project_root=str(ROOT),
            store=submission_store,
            protected_payload_store=payload_store,
        )
        first = service.preflight(
            authority_scope="LOCAL_RUN_SUBMITTER",
            agent_definition_id="reference-research-agent",
            request=RAW_REQUEST,
            model="acceptance-model",
            idempotency_key=IDEMPOTENCY_KEY,
        )
        replay = service.preflight(
            authority_scope="LOCAL_RUN_SUBMITTER",
            agent_definition_id="reference-research-agent",
            request=RAW_REQUEST,
            model="acceptance-model",
            idempotency_key=IDEMPOTENCY_KEY,
        )
        conflict_blocked = False
        try:
            service.preflight(
                authority_scope="LOCAL_RUN_SUBMITTER",
                agent_definition_id="reference-research-agent",
                request="different input",
                model="acceptance-model",
                idempotency_key=IDEMPOTENCY_KEY,
            )
        except RunSubmissionIdempotencyConflict:
            conflict_blocked = True
        reader_blocked = False
        try:
            service.preflight(
                authority_scope="LOCAL_OPERATIONS_READER",
                agent_definition_id="coding-agent",
                request="work",
                model=None,
                idempotency_key="step017-reader-scope-key-0001",
            )
        except RunSubmissionAuthorityError:
            reader_blocked = True

        project = workspace.scratch_dir / "local-tool-project"
        shutil.copytree(ROOT / "specs", project / "specs")
        definition_path = project / "specs" / "agents" / "coding-agent" / "definition.json"
        definition = json.loads(definition_path.read_text(encoding="utf-8"))
        definition["tools"] = ["controlled_local_tool"]
        definition_path.write_text(json.dumps(definition, indent=2) + "\n", encoding="utf-8")
        local_tool_store = SQLiteRunSubmissionStore(workspace.database_dir / "local-tool.sqlite3")
        local_tool_store.initialize()
        local_tool_payload_store = EncryptedFileProtectedPayloadStore(
            workspace.scratch_dir / "local-tool-protected",
            ProtectedPayloadKey.from_text(PAYLOAD_KEY),
        )
        local_tool_service = RunSubmissionBoundaryService(
            runtime_bindings=AgentRuntimeBindingCatalog(str(project)),
            project_root=str(project),
            store=local_tool_store,
            protected_payload_store=local_tool_payload_store,
        )
        local_tool = local_tool_service.preflight(
            authority_scope="LOCAL_RUN_SUBMITTER",
            agent_definition_id="coding-agent",
            request="controlled local tool work",
            model=None,
            idempotency_key="step017-local-tool-key-0001",
        )

        with TestClient(app) as client:
            policy_response = client.get("/v1/run-submission-policy", headers=HEADERS)
            direct_response = client.post(
                "/v1/runs",
                headers=HEADERS,
                json={"input": "must not execute", "confirm_live_call": True},
            )
            shell = client.get("/console")
            script = client.get("/console/assets/console.js")

        task_count, run_count, submission_count = _counts(product_db)
        database_bytes = product_db.read_bytes()
        references_after = {
            item.reference_id: item.to_dict()
            for item in ReferenceCatalogService(ROOT).verify_all()
        }
        policy = policy_response.json()
        checks = {
            "policy_endpoint_authenticated": policy_response.status_code == 200,
            "policy_secure_defaults": policy.get("direct_run_api_default_enabled") is False
            and policy.get("console_mutation_enabled") is False,
            "read_only_agent_immediate_after_confirmation": first.execution_mode
            is RunSubmissionExecutionMode.IMMEDIATE_AFTER_CONFIRMATION
            and first.executable_now
            and not first.approval_required,
            "fingerprint_confirmation_required": bool(first.confirmation_challenge)
            and service.confirmation_matches(first, first.confirmation_challenge or ""),
            "idempotent_replay_same_submission": replay.replayed
            and replay.submission_id == first.submission_id,
            "idempotency_conflict_blocked": conflict_blocked,
            "read_authority_cannot_submit": reader_blocked,
            "local_tool_requires_approval_interruption": local_tool.execution_mode
            is RunSubmissionExecutionMode.APPROVAL_INTERRUPTED
            and local_tool.approval_required
            and not local_tool.executable_now,
            "raw_payload_not_persisted": RAW_REQUEST.encode() not in database_bytes,
            "raw_idempotency_key_not_persisted": IDEMPOTENCY_KEY.encode() not in database_bytes,
            "preflight_creates_no_task_or_run": task_count == 0 and run_count == 0,
            "single_preflight_record_persisted": submission_count == 1,
            "direct_run_api_disabled": direct_response.status_code == 403
            and direct_response.json().get("code") == "DIRECT_RUN_SUBMISSION_DISABLED",
            "console_remains_read_only": "Run Submission Boundary" in shell.text
            and 'method:"POST"' not in script.text,
            "protected_payload_evolution_preserves_boundary": first.protected_payload_persisted is True
            and policy.get("protected_payload_mode") == "AES_256_GCM_FILE_V1"
            and local_tool.protected_payload_persisted is False,
            "references_unchanged": references_before == references_after,
        }
        payload: dict[str, object] = {
            "schema_version": "okcanvas-step017-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "submission": first.to_public_dict(),
            "local_tool_submission": local_tool.to_public_dict(),
            "task_count": task_count,
            "run_count": run_count,
            "submission_count": submission_count,
        }
        payload = workspace.finalize(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP017_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
