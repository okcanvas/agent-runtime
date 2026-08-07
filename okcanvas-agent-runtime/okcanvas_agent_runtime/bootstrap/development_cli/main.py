from __future__ import annotations

from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog, AgentDefinitionError
from okcanvas_agent_clients.operator import ApprovalOperatorConfig, ApprovalOperatorError, LocalApprovalOperatorClient
from okcanvas_agent_runtime.application.execution import GenericAgentExecutionService, GenericExecutionEnvelope, GenericExecutionErrorCode, OpenAIGenericAgentGateway
from okcanvas_agent_runtime.agent.tools.codex.readonly_contracts import CodexReadOnlyEnvelope, CodexReadOnlyErrorCode
from okcanvas_agent_runtime.agent.tools.codex.write_contracts import CodexWriteEnvelope, CodexWriteErrorCode
from okcanvas_agent_runtime.agent.tools.codex.approval_contracts import ApprovalDecision, ApprovalErrorCode, ApprovalPrepareEnvelope, ApprovalResumeEnvelope
from okcanvas_agent_runtime.core.config import CodexReadOnlySettings, CodexWriteSettings, RuntimeSettings
from okcanvas_agent_runtime.core.contracts import RunEnvelope, RuntimeErrorCode
from okcanvas_agent_runtime.adapters.evidence import write_run_evidence
from okcanvas_agent_runtime.core.errors import RuntimeFailure
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.adapters.openai.runtime import AgentRuntimeService, CodexReadOnlyService, OpenAIAgentsGateway, OpenAICodexReadOnlyGateway, CodexWriteService, OpenAICodexWriteGateway, CodexWriteApprovalService
from okcanvas_agent_runtime.adapters.openai.runtime.codex_readiness import inspect_codex_readiness
from okcanvas_agent_runtime.adapters.openai.runtime.sdk_readiness import inspect_sdk
from okcanvas_agent_runtime.agent.mcp.definitions import MCPDefinitionError, MCPServerCatalog
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.application.artifacts import ArtifactService
from okcanvas_agent_runtime.adapters.storage.artifacts import LocalFilesystemArtifactBlobStore
from okcanvas_agent_runtime.domain.runs import ProductStateError
from okcanvas_agent_runtime.application.evaluation import DeterministicEvaluator, EvaluationCatalog, EvaluationSuiteCatalog, EvaluationSuiteError, EvaluationSuiteService, EvaluationSuiteSubject, RecordedRunEvaluationError, RecordedRunEvaluationService, SQLiteEvaluationStore, compare_results
from okcanvas_agent_clients.tui import TUIClientError, run_tui_from_environment
from okcanvas_agent_runtime.adapters.reference_catalog import ProductStoreReferenceAccessRecorder, ReferenceCatalogError, ReferenceCatalogService, ReferenceIntegrityError, ReferenceManifestError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="okcanvas-agent-runtime")
    sub = parser.add_subparsers(dest="command", required=True)

    info = sub.add_parser("info", help="Print the current runtime capability baseline")
    info.add_argument("--pretty", action="store_true")

    doctor = sub.add_parser("doctor", help="Check minimal Agent live-run readiness")
    doctor.add_argument("--model")
    doctor.add_argument("--pretty", action="store_true")

    tui = sub.add_parser(
        "tui",
        help="Open the loopback-only governed terminal client",
    )
    tui.add_argument("--base-url")
    tui.add_argument("--agent-id")
    tui.add_argument("--model")
    tui.add_argument("--evaluation-case-id")

    run = sub.add_parser("run", help="Execute one explicitly confirmed tool-free Agent run")
    input_group = run.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input")
    input_group.add_argument("--input-file", type=Path)
    run.add_argument("--model")
    run.add_argument("--request-id")
    run.add_argument("--confirm-live-call", action="store_true")
    run.add_argument("--evidence-file", type=Path)
    run.add_argument("--pretty", action="store_true")

    definition_show = sub.add_parser(
        "agent-definition-show", help="Resolve one immutable declarative Agent definition"
    )
    definition_show.add_argument("--project-root", type=Path, default=Path("."))
    definition_show.add_argument("--agent-id", default="coding-agent")
    definition_show.add_argument("--pretty", action="store_true")

    generic_run = sub.add_parser(
        "generic-agent-run", help="Execute one persisted generic Agent Run"
    )
    generic_input = generic_run.add_mutually_exclusive_group(required=True)
    generic_input.add_argument("--input")
    generic_input.add_argument("--input-file", type=Path)
    generic_run.add_argument("--project-root", type=Path, default=Path("."))
    generic_run.add_argument("--agent-id", default="coding-agent")
    generic_run.add_argument("--model")
    generic_run.add_argument("--product-db", type=Path, required=True)
    generic_run.add_argument("--artifact-root", type=Path, required=True)
    generic_run.add_argument("--confirm-live-call", action="store_true")
    generic_run.add_argument("--pretty", action="store_true")


    mcp_show = sub.add_parser(
        "mcp-server-show", help="Resolve one immutable allowlisted MCP server definition"
    )
    mcp_show.add_argument("--project-root", type=Path, default=Path("."))
    mcp_show.add_argument("--server-id", default="reference-catalog")
    mcp_show.add_argument("--pretty", action="store_true")

    codex_doctor = sub.add_parser(
        "codex-doctor", help="Check official SDK and Codex CLI read-only readiness"
    )
    codex_doctor.add_argument("--agent-model")
    codex_doctor.add_argument("--codex-model")
    codex_doctor.add_argument("--codex-path")
    codex_doctor.add_argument("--pretty", action="store_true")

    codex_run = sub.add_parser(
        "codex-readonly", help="Run the experimental official Codex Tool in read-only mode"
    )
    codex_input = codex_run.add_mutually_exclusive_group(required=True)
    codex_input.add_argument("--input")
    codex_input.add_argument("--input-file", type=Path)
    codex_run.add_argument("--workspace", type=Path, required=True)
    codex_run.add_argument("--agent-model")
    codex_run.add_argument("--codex-model")
    codex_run.add_argument("--codex-path")
    codex_run.add_argument("--request-id")
    codex_run.add_argument("--confirm-live-call", action="store_true")
    codex_run.add_argument("--confirm-controlled-workspace", action="store_true")
    codex_run.add_argument("--event-file", type=Path, required=True)
    codex_run.add_argument("--thread-state-file", type=Path)
    codex_run.add_argument("--evidence-file", type=Path)
    codex_run.add_argument("--require-file", action="append", default=[])
    codex_run.add_argument("--pretty", action="store_true")

    codex_write = sub.add_parser(
        "codex-write", help="Run Codex in an explicitly approved disposable workspace"
    )
    write_input = codex_write.add_mutually_exclusive_group(required=True)
    write_input.add_argument("--input")
    write_input.add_argument("--input-file", type=Path)
    codex_write.add_argument("--workspace", type=Path, required=True)
    codex_write.add_argument("--agent-model")
    codex_write.add_argument("--codex-model")
    codex_write.add_argument("--codex-path")
    codex_write.add_argument("--request-id")
    codex_write.add_argument("--confirm-live-call", action="store_true")
    codex_write.add_argument("--confirm-controlled-workspace", action="store_true")
    codex_write.add_argument("--confirm-disposable-workspace", action="store_true")
    codex_write.add_argument("--confirm-workspace-write", action="store_true")
    codex_write.add_argument("--event-file", type=Path, required=True)
    codex_write.add_argument("--patch-file", type=Path, required=True)
    codex_write.add_argument("--evidence-file", type=Path)
    codex_write.add_argument("--allow-file", action="append", default=[])
    codex_write.add_argument("--expect-file", action="append", default=[])
    codex_write.add_argument("--pretty", action="store_true")

    approval_prepare = sub.add_parser(
        "codex-approval-prepare",
        help="Create a persisted whole-run approval interruption before Codex write",
    )
    approval_input = approval_prepare.add_mutually_exclusive_group(required=True)
    approval_input.add_argument("--input")
    approval_input.add_argument("--input-file", type=Path)
    approval_prepare.add_argument("--workspace", type=Path, required=True)
    approval_prepare.add_argument("--agent-model")
    approval_prepare.add_argument("--codex-model")
    approval_prepare.add_argument("--codex-path")
    approval_prepare.add_argument("--request-id")
    approval_prepare.add_argument("--confirm-live-call", action="store_true")
    approval_prepare.add_argument("--confirm-controlled-workspace", action="store_true")
    approval_prepare.add_argument("--confirm-disposable-workspace", action="store_true")
    approval_prepare.add_argument("--confirm-workspace-write", action="store_true")
    approval_prepare.add_argument("--state-file", type=Path, required=True)
    approval_prepare.add_argument("--approval-file", type=Path, required=True)
    approval_prepare.add_argument("--event-file", type=Path, required=True)
    approval_prepare.add_argument("--patch-file", type=Path, required=True)
    approval_prepare.add_argument("--write-evidence-file", type=Path, required=True)
    approval_prepare.add_argument("--evidence-file", type=Path)
    approval_prepare.add_argument("--allow-file", action="append", default=[])
    approval_prepare.add_argument("--expect-file", action="append", default=[])
    approval_prepare.add_argument("--pretty", action="store_true")

    approval_resume = sub.add_parser(
        "codex-approval-resume",
        help="Load persisted RunState and approve or reject the whole Codex write",
    )
    approval_resume.add_argument("--approval-file", type=Path, required=True)
    approval_resume.add_argument(
        "--decision", choices=["approve", "reject"], required=True
    )
    approval_resume.add_argument("--agent-model")
    approval_resume.add_argument("--codex-model")
    approval_resume.add_argument("--codex-path")
    approval_resume.add_argument("--evidence-file", type=Path)
    approval_resume.add_argument("--pretty", action="store_true")

    approval_inbox = sub.add_parser(
        "approval-inbox-list",
        help="List bounded approval metadata from the loopback Control API",
    )
    approval_inbox.add_argument("--base-url")
    approval_inbox.add_argument(
        "--state",
        choices=["PENDING", "APPROVING", "REJECTING", "APPROVED", "REJECTED", "SUCCEEDED", "FAILED", "ALL"],
        default="PENDING",
    )
    approval_inbox.add_argument("--limit", type=int, default=20)
    approval_inbox.add_argument("--offset", type=int, default=0)
    approval_inbox.add_argument("--pretty", action="store_true")

    approval_decide = sub.add_parser(
        "approval-decide",
        help="Approve or reject one pending local Tool call through the loopback Control API",
    )
    approval_decide.add_argument("--base-url")
    approval_decide.add_argument("--approval-id", required=True)
    approval_decide.add_argument("--decision", choices=["APPROVE", "REJECT", "approve", "reject"], required=True)
    approval_decide.add_argument("--confirmation", required=True)
    approval_decide.add_argument("--pretty", action="store_true")

    evaluation_run = sub.add_parser("evaluation-run", help="Deterministically evaluate one recorded execution")
    evaluation_run.add_argument("--project-root", type=Path, default=Path("."))
    evaluation_run.add_argument("--case-id", required=True)
    evaluation_run.add_argument("--envelope-file", type=Path, required=True)
    evaluation_run.add_argument("--events-file", type=Path, required=True)
    evaluation_run.add_argument("--duration-ms", type=int, required=True)
    evaluation_run.add_argument("--evaluation-db", type=Path, required=True)
    evaluation_run.add_argument("--pretty", action="store_true")

    recorded_evaluation = sub.add_parser(
        "evaluation-run-recorded",
        help="Evaluate one completed Product Run from persisted Events and final-output Artifact",
    )
    recorded_evaluation.add_argument("--project-root", type=Path, default=Path("."))
    recorded_evaluation.add_argument("--run-id", required=True)
    recorded_evaluation.add_argument("--case-id", required=True)
    recorded_evaluation.add_argument("--product-db", type=Path, required=True)
    recorded_evaluation.add_argument("--artifact-root", type=Path, required=True)
    recorded_evaluation.add_argument("--evaluation-db", type=Path, required=True)
    recorded_evaluation.add_argument("--pretty", action="store_true")

    evaluation_list = sub.add_parser("evaluation-list", help="List persisted evaluation history for a case")
    evaluation_list.add_argument("--case-id", required=True)
    evaluation_list.add_argument("--evaluation-db", type=Path, required=True)
    evaluation_list.add_argument("--pretty", action="store_true")

    suite_list = sub.add_parser("evaluation-suite-list", help="List immutable Evaluation Suite definitions")
    suite_list.add_argument("--project-root", type=Path, default=Path("."))
    suite_list.add_argument("--pretty", action="store_true")

    suite_show = sub.add_parser("evaluation-suite-show", help="Resolve one immutable Evaluation Suite")
    suite_show.add_argument("--project-root", type=Path, default=Path("."))
    suite_show.add_argument("--suite-id", required=True)
    suite_show.add_argument("--pretty", action="store_true")

    suite_run = sub.add_parser("evaluation-suite-run", help="Evaluate a bounded explicit batch of completed Product Runs")
    suite_run.add_argument("--project-root", type=Path, default=Path("."))
    suite_run.add_argument("--suite-id", required=True)
    suite_run.add_argument("--subject", action="append", required=True, help="subject_id=slot_id=run_id")
    suite_run.add_argument("--baseline-id")
    suite_run.add_argument("--product-db", type=Path, required=True)
    suite_run.add_argument("--artifact-root", type=Path, required=True)
    suite_run.add_argument("--evaluation-db", type=Path, required=True)
    suite_run.add_argument("--pretty", action="store_true")

    suite_run_show = sub.add_parser("evaluation-suite-run-show", help="Show one persisted Evaluation Suite execution")
    suite_run_show.add_argument("--suite-run-id", required=True)
    suite_run_show.add_argument("--evaluation-db", type=Path, required=True)
    suite_run_show.add_argument("--pretty", action="store_true")

    baseline_create = sub.add_parser("evaluation-baseline-create", help="Create an explicit immutable Baseline from a passed Suite run")
    baseline_create.add_argument("--project-root", type=Path, default=Path("."))
    baseline_create.add_argument("--source-suite-run-id", required=True)
    baseline_create.add_argument("--label", required=True)
    baseline_create.add_argument("--product-db", type=Path, required=True)
    baseline_create.add_argument("--artifact-root", type=Path, required=True)
    baseline_create.add_argument("--evaluation-db", type=Path, required=True)
    baseline_create.add_argument("--pretty", action="store_true")

    baseline_show = sub.add_parser("evaluation-baseline-show", help="Show one immutable Evaluation Baseline")
    baseline_show.add_argument("--baseline-id", required=True)
    baseline_show.add_argument("--evaluation-db", type=Path, required=True)
    baseline_show.add_argument("--pretty", action="store_true")

    reference_list = sub.add_parser(
        "reference-list", help="List manifest-declared immutable reference sources"
    )
    reference_list.add_argument("--project-root", type=Path, default=Path("."))
    reference_list.add_argument("--pretty", action="store_true")

    reference_verify = sub.add_parser(
        "reference-verify", help="Verify immutable reference tree integrity"
    )
    reference_verify.add_argument("--project-root", type=Path, default=Path("."))
    reference_verify.add_argument("--reference-id", action="append", default=[])
    reference_verify.add_argument("--pretty", action="store_true")

    reference_search = sub.add_parser(
        "reference-search", help="Search bounded UTF-8 text in verified reference trees"
    )
    reference_search.add_argument("query")
    reference_search.add_argument("--project-root", type=Path, default=Path("."))
    reference_search.add_argument("--reference-id", action="append", default=[])
    reference_search.add_argument("--max-results", type=int, default=20)
    reference_search.add_argument("--max-file-bytes", type=int, default=1_048_576)
    reference_search.add_argument("--product-db", type=Path)
    reference_search.add_argument("--run-id")
    reference_search.add_argument("--pretty", action="store_true")

    reference_read = sub.add_parser(
        "reference-read", help="Read an exact bounded line range from a verified reference file"
    )
    reference_read.add_argument("--project-root", type=Path, default=Path("."))
    reference_read.add_argument("--reference-id", required=True)
    reference_read.add_argument("--path", required=True)
    reference_read.add_argument("--start-line", type=int, required=True)
    reference_read.add_argument("--end-line", type=int, required=True)
    reference_read.add_argument("--max-lines", type=int, default=400)
    reference_read.add_argument("--max-file-bytes", type=int, default=2_097_152)
    reference_read.add_argument("--product-db", type=Path)
    reference_read.add_argument("--run-id")
    reference_read.add_argument("--pretty", action="store_true")
    return parser


def _json_print(payload: object, *, pretty: bool) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True))


def _read_request(args: argparse.Namespace) -> str:
    if args.input is not None:
        return args.input
    try:
        return args.input_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeFailure(
            RuntimeErrorCode.INVALID_REQUEST,
            "Unable to read the request input file",
            detail_type=type(exc).__name__,
        ) from exc


def _exit_code(envelope: RunEnvelope) -> int:
    if envelope.state == "SUCCEEDED":
        return 0
    assert envelope.error is not None
    if envelope.error.code in {
        RuntimeErrorCode.INVALID_REQUEST,
        RuntimeErrorCode.LIVE_OPT_IN_REQUIRED,
        RuntimeErrorCode.API_KEY_MISSING,
        RuntimeErrorCode.MODEL_NOT_CONFIGURED,
    }:
        return 2
    if envelope.error.code in {
        RuntimeErrorCode.SDK_NOT_INSTALLED,
        RuntimeErrorCode.SDK_VERSION_MISMATCH,
    }:
        return 3
    return 4


def _codex_exit_code(envelope: CodexReadOnlyEnvelope) -> int:
    if envelope.state == "SUCCEEDED":
        return 0
    assert envelope.error is not None
    if envelope.error.code in {
        CodexReadOnlyErrorCode.INVALID_REQUEST,
        CodexReadOnlyErrorCode.LIVE_OPT_IN_REQUIRED,
        CodexReadOnlyErrorCode.WORKSPACE_TRUST_OPT_IN_REQUIRED,
        CodexReadOnlyErrorCode.WORKSPACE_NOT_FOUND,
        CodexReadOnlyErrorCode.GIT_REPOSITORY_REQUIRED,
        CodexReadOnlyErrorCode.WORKSPACE_SYMLINK_NOT_ALLOWED,
        CodexReadOnlyErrorCode.API_KEY_MISSING,
        CodexReadOnlyErrorCode.AGENT_MODEL_NOT_CONFIGURED,
        CodexReadOnlyErrorCode.CODEX_MODEL_NOT_CONFIGURED,
        CodexReadOnlyErrorCode.THREAD_STATE_INVALID,
    }:
        return 2
    if envelope.error.code in {
        CodexReadOnlyErrorCode.SDK_NOT_INSTALLED,
        CodexReadOnlyErrorCode.SDK_VERSION_MISMATCH,
        CodexReadOnlyErrorCode.CODEX_CLI_NOT_INSTALLED,
        CodexReadOnlyErrorCode.CODEX_CLI_VERSION_UNREADABLE,
    }:
        return 3
    return 4


def _codex_write_exit_code(envelope: CodexWriteEnvelope) -> int:
    if envelope.state == "SUCCEEDED":
        return 0
    assert envelope.error is not None
    if envelope.error.code in {
        CodexWriteErrorCode.INVALID_REQUEST,
        CodexWriteErrorCode.LIVE_OPT_IN_REQUIRED,
        CodexWriteErrorCode.WORKSPACE_TRUST_OPT_IN_REQUIRED,
        CodexWriteErrorCode.DISPOSABLE_WORKSPACE_OPT_IN_REQUIRED,
        CodexWriteErrorCode.WORKSPACE_WRITE_OPT_IN_REQUIRED,
        CodexWriteErrorCode.WORKSPACE_NOT_FOUND,
        CodexWriteErrorCode.GIT_REPOSITORY_REQUIRED,
        CodexWriteErrorCode.WORKSPACE_NOT_CLEAN,
        CodexWriteErrorCode.WORKSPACE_SYMLINK_NOT_ALLOWED,
        CodexWriteErrorCode.API_KEY_MISSING,
        CodexWriteErrorCode.AGENT_MODEL_NOT_CONFIGURED,
        CodexWriteErrorCode.CODEX_MODEL_NOT_CONFIGURED,
    }:
        return 2
    if envelope.error.code in {
        CodexWriteErrorCode.SDK_NOT_INSTALLED,
        CodexWriteErrorCode.SDK_VERSION_MISMATCH,
        CodexWriteErrorCode.CODEX_CLI_NOT_INSTALLED,
        CodexWriteErrorCode.CODEX_CLI_VERSION_UNREADABLE,
    }:
        return 3
    return 4


def _approval_prepare_exit_code(envelope: ApprovalPrepareEnvelope) -> int:
    if envelope.state == "AWAITING_APPROVAL":
        return 0
    assert envelope.error is not None
    if envelope.error.code in {
        ApprovalErrorCode.INVALID_REQUEST,
        ApprovalErrorCode.LIVE_OPT_IN_REQUIRED,
        ApprovalErrorCode.WORKSPACE_TRUST_OPT_IN_REQUIRED,
        ApprovalErrorCode.DISPOSABLE_WORKSPACE_OPT_IN_REQUIRED,
        ApprovalErrorCode.WORKSPACE_WRITE_OPT_IN_REQUIRED,
        ApprovalErrorCode.WORKSPACE_NOT_FOUND,
        ApprovalErrorCode.GIT_REPOSITORY_REQUIRED,
        ApprovalErrorCode.WORKSPACE_NOT_CLEAN,
        ApprovalErrorCode.WORKSPACE_SYMLINK_NOT_ALLOWED,
        ApprovalErrorCode.ARTIFACT_PATH_INSIDE_WORKSPACE,
        ApprovalErrorCode.APPROVAL_ARTIFACT_EXISTS,
        ApprovalErrorCode.API_KEY_MISSING,
        ApprovalErrorCode.AGENT_MODEL_NOT_CONFIGURED,
        ApprovalErrorCode.CODEX_MODEL_NOT_CONFIGURED,
    }:
        return 2
    if envelope.error.code in {
        ApprovalErrorCode.SDK_NOT_INSTALLED,
        ApprovalErrorCode.SDK_VERSION_MISMATCH,
        ApprovalErrorCode.CODEX_CLI_NOT_INSTALLED,
        ApprovalErrorCode.CODEX_CLI_VERSION_UNREADABLE,
    }:
        return 3
    return 4


def _approval_resume_exit_code(envelope: ApprovalResumeEnvelope) -> int:
    if envelope.state in {"SUCCEEDED", "REJECTED"}:
        return 0
    assert envelope.error is not None
    if envelope.error.code in {
        ApprovalErrorCode.APPROVAL_RECORD_NOT_FOUND,
        ApprovalErrorCode.RUN_STATE_NOT_FOUND,
        ApprovalErrorCode.RUN_STATE_HASH_MISMATCH,
        ApprovalErrorCode.APPROVAL_ALREADY_DECIDED,
        ApprovalErrorCode.APPROVAL_STATE_INVALID,
        ApprovalErrorCode.API_KEY_MISSING,
        ApprovalErrorCode.AGENT_MODEL_NOT_CONFIGURED,
        ApprovalErrorCode.CODEX_MODEL_NOT_CONFIGURED,
    }:
        return 2
    if envelope.error.code in {
        ApprovalErrorCode.SDK_NOT_INSTALLED,
        ApprovalErrorCode.SDK_VERSION_MISMATCH,
        ApprovalErrorCode.CODEX_CLI_NOT_INSTALLED,
        ApprovalErrorCode.CODEX_CLI_VERSION_UNREADABLE,
    }:
        return 3
    return 4


async def _run_live(args: argparse.Namespace) -> tuple[RunEnvelope, int]:
    settings = RuntimeSettings.from_env(model_override=args.model)
    service = AgentRuntimeService(OpenAIAgentsGateway())
    try:
        request = _read_request(args)
    except RuntimeFailure as failure:
        request = ""
        envelope = await service.run(
            request=request,
            settings=settings,
            live_opt_in=False,
            request_id=args.request_id,
        )
        if envelope.error is not None:
            envelope.error.code = failure.code
            envelope.error.message = failure.public_message
            envelope.error.detail_type = failure.detail_type
        return envelope, 2

    envelope = await service.run(
        request=request,
        settings=settings,
        live_opt_in=args.confirm_live_call,
        request_id=args.request_id,
    )
    if args.evidence_file is not None:
        try:
            write_run_evidence(args.evidence_file, envelope)
        except RuntimeFailure as failure:
            print(
                json.dumps(
                    {
                        "code": failure.code.value,
                        "message": failure.public_message,
                        "detail_type": failure.detail_type,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return envelope, 4
    return envelope, _exit_code(envelope)


def _generic_exit_code(envelope: GenericExecutionEnvelope) -> int:
    if envelope.state == "SUCCEEDED":
        return 0
    assert envelope.error is not None
    if envelope.error.code in {
        GenericExecutionErrorCode.INVALID_REQUEST,
        GenericExecutionErrorCode.LIVE_OPT_IN_REQUIRED,
        GenericExecutionErrorCode.AGENT_DEFINITION_INVALID,
        GenericExecutionErrorCode.AGENT_POLICY_DENIED,
        GenericExecutionErrorCode.MCP_CONFIGURATION_INVALID,
        GenericExecutionErrorCode.API_KEY_MISSING,
        GenericExecutionErrorCode.MODEL_NOT_CONFIGURED,
    }:
        return 2
    if envelope.error.code in {
        GenericExecutionErrorCode.SDK_NOT_INSTALLED,
        GenericExecutionErrorCode.SDK_VERSION_MISMATCH,
    }:
        return 3
    return 4


async def _run_generic(args: argparse.Namespace) -> tuple[GenericExecutionEnvelope, int]:
    try:
        request = _read_request(args)
    except RuntimeFailure:
        request = ""
    store = SQLiteProductStore(args.product_db)
    store.initialize()
    service = GenericAgentExecutionService(
        runtime_bindings=AgentRuntimeBindingCatalog(args.project_root),
        definitions=AgentDefinitionCatalog(args.project_root),
        store=store,
        gateway=OpenAIGenericAgentGateway(),
        artifact_root=args.artifact_root,
        artifact_service=ArtifactService(
            product_store=store,
            blob_store=LocalFilesystemArtifactBlobStore(args.artifact_root),
        ),
    )
    envelope = await service.run(
        agent_definition_id=args.agent_id,
        request=request,
        settings=RuntimeSettings.from_env(model_override=args.model),
        live_opt_in=args.confirm_live_call,
    )
    return envelope, _generic_exit_code(envelope)


async def _run_codex_readonly(args: argparse.Namespace) -> tuple[CodexReadOnlyEnvelope, int]:
    settings = CodexReadOnlySettings.from_env(
        agent_model_override=args.agent_model,
        codex_model_override=args.codex_model,
        codex_path_override=args.codex_path,
    )
    service = CodexReadOnlyService(OpenAICodexReadOnlyGateway())
    try:
        request = _read_request(args)
    except RuntimeFailure:
        request = ""
    envelope = await service.run(
        request=request,
        settings=settings,
        workspace=args.workspace,
        event_file=args.event_file,
        thread_state_file=args.thread_state_file,
        live_opt_in=args.confirm_live_call,
        trusted_workspace_opt_in=args.confirm_controlled_workspace,
        required_files=tuple(args.require_file),
        artifact_paths=(args.evidence_file,) if args.evidence_file is not None else (),
        request_id=args.request_id,
    )
    if args.evidence_file is not None:
        try:
            write_run_evidence(args.evidence_file, envelope)
        except RuntimeFailure as failure:
            print(
                json.dumps(
                    {
                        "code": failure.code.value,
                        "message": failure.public_message,
                        "detail_type": failure.detail_type,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return envelope, 4
    return envelope, _codex_exit_code(envelope)


async def _run_codex_write(args: argparse.Namespace) -> tuple[CodexWriteEnvelope, int]:
    settings = CodexWriteSettings.from_env(
        agent_model_override=args.agent_model,
        codex_model_override=args.codex_model,
        codex_path_override=args.codex_path,
    )
    service = CodexWriteService(OpenAICodexWriteGateway())
    try:
        request = _read_request(args)
    except RuntimeFailure:
        request = ""
    envelope = await service.run(
        request=request,
        settings=settings,
        workspace=args.workspace,
        event_file=args.event_file,
        patch_file=args.patch_file,
        live_opt_in=args.confirm_live_call,
        trusted_workspace_opt_in=args.confirm_controlled_workspace,
        disposable_workspace_opt_in=args.confirm_disposable_workspace,
        workspace_write_opt_in=args.confirm_workspace_write,
        allowed_files=tuple(args.allow_file),
        expected_files=tuple(args.expect_file),
        artifact_paths=(args.evidence_file,) if args.evidence_file is not None else (),
        request_id=args.request_id,
    )
    if args.evidence_file is not None:
        try:
            write_run_evidence(args.evidence_file, envelope)
        except RuntimeFailure as failure:
            print(
                json.dumps(
                    {
                        "code": failure.code.value,
                        "message": failure.public_message,
                        "detail_type": failure.detail_type,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return envelope, 4
    return envelope, _codex_write_exit_code(envelope)



async def _run_approval_prepare(args: argparse.Namespace) -> tuple[ApprovalPrepareEnvelope, int]:
    settings = CodexWriteSettings.from_env(
        agent_model_override=args.agent_model,
        codex_model_override=args.codex_model,
        codex_path_override=args.codex_path,
    )
    try:
        request = _read_request(args)
    except RuntimeFailure:
        request = ""
    envelope = await CodexWriteApprovalService().prepare(
        request=request,
        settings=settings,
        workspace=args.workspace,
        state_file=args.state_file,
        approval_file=args.approval_file,
        event_file=args.event_file,
        patch_file=args.patch_file,
        write_evidence_file=args.write_evidence_file,
        live_opt_in=args.confirm_live_call,
        trusted_workspace_opt_in=args.confirm_controlled_workspace,
        disposable_workspace_opt_in=args.confirm_disposable_workspace,
        workspace_write_opt_in=args.confirm_workspace_write,
        allowed_files=tuple(args.allow_file),
        expected_files=tuple(args.expect_file),
        request_id=args.request_id,
    )
    if args.evidence_file is not None:
        write_run_evidence(args.evidence_file, envelope)
    return envelope, _approval_prepare_exit_code(envelope)


async def _run_approval_resume(args: argparse.Namespace) -> tuple[ApprovalResumeEnvelope, int]:
    settings = CodexWriteSettings.from_env(
        agent_model_override=args.agent_model,
        codex_model_override=args.codex_model,
        codex_path_override=args.codex_path,
    )
    decision = (
        ApprovalDecision.APPROVE
        if args.decision == "approve"
        else ApprovalDecision.REJECT
    )
    envelope = await CodexWriteApprovalService().resume(
        settings=settings,
        approval_file=args.approval_file,
        decision=decision,
    )
    if args.evidence_file is not None:
        write_run_evidence(args.evidence_file, envelope)
    return envelope, _approval_resume_exit_code(envelope)


def _reference_catalog(args: argparse.Namespace) -> ReferenceCatalogService:
    if (args.product_db is None) != (args.run_id is None):
        raise ReferenceCatalogError(
            "--product-db and --run-id must be supplied together"
        )
    recorder = None
    if args.product_db is not None:
        store = SQLiteProductStore(args.product_db)
        store.initialize()
        recorder = ProductStoreReferenceAccessRecorder(store)
    return ReferenceCatalogService(args.project_root, recorder=recorder)


def _reference_error_exit(error: Exception) -> int:
    payload = {
        "code": getattr(error, "code", "REFERENCE_COMMAND_ERROR"),
        "message": str(error),
        "details": getattr(error, "details", {}),
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), file=sys.stderr)
    if isinstance(error, (ReferenceManifestError, ReferenceIntegrityError)):
        return 3
    return 2

def _parse_suite_subjects(values: Sequence[str]) -> tuple[EvaluationSuiteSubject, ...]:
    subjects: list[EvaluationSuiteSubject] = []
    for value in values:
        parts = value.split("=", 2)
        if len(parts) != 3 or not all(parts):
            raise ValueError("suite subject must use subject_id=slot_id=run_id")
        subjects.append(EvaluationSuiteSubject(parts[0], parts[1], parts[2]))
    return tuple(subjects)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "info":
        _json_print(RuntimeInfo().to_dict(), pretty=args.pretty)
        return 0
    if args.command == "doctor":
        readiness = inspect_sdk(RuntimeSettings.from_env(model_override=args.model))
        _json_print(readiness.to_dict(), pretty=args.pretty)
        return 0 if readiness.ready else 3
    if args.command == "tui":
        try:
            return run_tui_from_environment(
                base_url=args.base_url,
                agent_id=args.agent_id,
                model=args.model,
                evaluation_case_id=args.evaluation_case_id,
            )
        except TUIClientError as error:
            print(
                json.dumps(
                    {"code": error.code, "message": error.message},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 3 if error.code == "TUI_CONNECTION_FAILED" else 2
        except (EOFError, KeyboardInterrupt):
            print("TUI cancelled", file=sys.stderr)
            return 130
    if args.command == "run":
        envelope, exit_code = asyncio.run(_run_live(args))
        print(envelope.model_dump_json(indent=2 if args.pretty else None))
        return exit_code
    if args.command == "agent-definition-show":
        try:
            definition = AgentDefinitionCatalog(args.project_root).resolve(args.agent_id)
            _json_print(definition.to_public_dict(), pretty=args.pretty)
            return 0
        except (AgentDefinitionError, OSError) as error:
            print(
                json.dumps(
                    {
                        "code": "AGENT_DEFINITION_INVALID",
                        "message": str(error),
                        "detail_type": type(error).__name__,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 2
    if args.command == "generic-agent-run":
        envelope, exit_code = asyncio.run(_run_generic(args))
        print(envelope.model_dump_json(indent=2 if args.pretty else None))
        return exit_code
    if args.command == "mcp-server-show":
        try:
            definition = MCPServerCatalog(args.project_root).resolve(args.server_id)
            _json_print(definition.to_public_dict(), pretty=args.pretty)
            return 0
        except (MCPDefinitionError, OSError) as error:
            print(
                json.dumps(
                    {
                        "code": "MCP_CONFIGURATION_INVALID",
                        "message": str(error),
                        "detail_type": type(error).__name__,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 2
    if args.command == "codex-doctor":
        settings = CodexReadOnlySettings.from_env(
            agent_model_override=args.agent_model,
            codex_model_override=args.codex_model,
            codex_path_override=args.codex_path,
        )
        readiness = inspect_codex_readiness(settings)
        _json_print(readiness.to_dict(), pretty=args.pretty)
        return 0 if readiness.ready else 3
    if args.command == "codex-readonly":
        envelope, exit_code = asyncio.run(_run_codex_readonly(args))
        print(envelope.model_dump_json(indent=2 if args.pretty else None))
        return exit_code
    if args.command == "codex-write":
        envelope, exit_code = asyncio.run(_run_codex_write(args))
        print(envelope.model_dump_json(indent=2 if args.pretty else None))
        return exit_code
    if args.command == "codex-approval-prepare":
        envelope, exit_code = asyncio.run(_run_approval_prepare(args))
        print(envelope.model_dump_json(indent=2 if args.pretty else None))
        return exit_code
    if args.command == "codex-approval-resume":
        envelope, exit_code = asyncio.run(_run_approval_resume(args))
        print(envelope.model_dump_json(indent=2 if args.pretty else None))
        return exit_code
    if args.command == "approval-inbox-list":
        try:
            config = ApprovalOperatorConfig.from_env(
                base_url_override=args.base_url,
                require_submitter=False,
            )
            with LocalApprovalOperatorClient(config) as client:
                payload = client.list_approvals(
                    state=None if args.state == "ALL" else args.state,
                    limit=args.limit,
                    offset=args.offset,
                )
            _json_print(payload, pretty=args.pretty)
            return 0
        except ApprovalOperatorError as error:
            print(
                json.dumps(
                    {"code": error.code, "message": error.message},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 3 if error.code == "APPROVAL_OPERATOR_CONNECTION_FAILED" else 2
    if args.command == "approval-decide":
        try:
            config = ApprovalOperatorConfig.from_env(
                base_url_override=args.base_url,
                require_submitter=True,
            )
            with LocalApprovalOperatorClient(config) as client:
                payload = client.decide(
                    approval_id=args.approval_id,
                    decision=args.decision,
                    confirmation=args.confirmation,
                )
            _json_print(payload, pretty=args.pretty)
            return 0
        except ApprovalOperatorError as error:
            print(
                json.dumps(
                    {"code": error.code, "message": error.message},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 3 if error.code == "APPROVAL_OPERATOR_CONNECTION_FAILED" else 2
    if args.command == "evaluation-run":
        try:
            case = EvaluationCatalog(args.project_root).resolve(args.case_id)
            envelope = json.loads(args.envelope_file.read_text(encoding="utf-8"))
            events_payload = json.loads(args.events_file.read_text(encoding="utf-8"))
            events = events_payload.get("events", events_payload) if isinstance(events_payload, dict) else events_payload
            result = DeterministicEvaluator().evaluate(case=case, envelope=envelope, events=events, duration_ms=args.duration_ms)
            store = SQLiteEvaluationStore(args.evaluation_db)
            store.initialize()
            store.save(case=case, envelope=envelope, result=result)
            _json_print({
                "evaluation_id": result.evaluation_id, "case_id": result.case_id, "case_version": result.case_version,
                "subject_run_id": result.subject_run_id, "state": result.state, "checks": result.checks,
                "metrics": result.metrics, "failures": list(result.failures), "created_at": result.created_at,
            }, pretty=args.pretty)
            return 0 if result.state == "PASSED" else 1
        except (ValueError, OSError, json.JSONDecodeError) as error:
            print(json.dumps({"code":"EVALUATION_INVALID","message":str(error)}, ensure_ascii=False), file=sys.stderr)
            return 2
    if args.command == "evaluation-run-recorded":
        product_store = SQLiteProductStore(args.product_db)
        product_store.initialize()
        evaluation_store = SQLiteEvaluationStore(args.evaluation_db)
        evaluation_store.initialize()
        service = RecordedRunEvaluationService(
            project_root=args.project_root,
            product_store=product_store,
            evaluation_store=evaluation_store,
            artifact_root=args.artifact_root,
            runtime_bindings=AgentRuntimeBindingCatalog(args.project_root),
            artifact_service=ArtifactService(
                product_store=product_store,
                blob_store=LocalFilesystemArtifactBlobStore(args.artifact_root),
            ),
        )
        try:
            outcome = service.evaluate(run_id=args.run_id, case_id=args.case_id)
            row = evaluation_store.get(outcome.evaluation.evaluation_id)
            _json_print(
                {
                    "schema_version": "okcanvas-recorded-run-evaluation-v1",
                    "evaluation": row,
                    "artifact_id": outcome.artifact_id,
                    "artifact_sha256": outcome.artifact_sha256,
                    "duration_ms": outcome.duration_ms,
                    "event_count": outcome.event_count,
                    "model": outcome.model,
                },
                pretty=args.pretty,
            )
            return 0 if outcome.evaluation.state == "PASSED" else 1
        except RecordedRunEvaluationError as error:
            print(
                json.dumps(
                    {
                        "code": error.code.value,
                        "message": error.message,
                        "detail_type": error.detail_type,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 2
    if args.command == "evaluation-list":
        store = SQLiteEvaluationStore(args.evaluation_db)
        store.initialize()
        _json_print({"results": store.list_case(args.case_id)}, pretty=args.pretty)
        return 0
    if args.command == "evaluation-suite-list":
        try:
            catalog = EvaluationSuiteCatalog(args.project_root)
            _json_print(
                {"suites": [
                    {
                        "suite_id": item.suite_id,
                        "version": item.version,
                        "max_subjects": item.max_subjects,
                        "slots": [slot.__dict__ for slot in item.slots],
                        "baseline_comparison": item.comparison.__dict__,
                        "manifest_sha256": item.manifest_sha256,
                    }
                    for item in catalog.list_suites()
                ]},
                pretty=args.pretty,
            )
            return 0
        except (ValueError, OSError, json.JSONDecodeError) as error:
            print(json.dumps({"code":"EVALUATION_SUITE_INVALID","message":str(error)}, ensure_ascii=False), file=sys.stderr)
            return 2
    if args.command == "evaluation-suite-show":
        try:
            item = EvaluationSuiteCatalog(args.project_root).resolve(args.suite_id)
            _json_print({
                "suite_id": item.suite_id,
                "version": item.version,
                "max_subjects": item.max_subjects,
                "slots": [slot.__dict__ for slot in item.slots],
                "baseline_comparison": item.comparison.__dict__,
                "manifest_sha256": item.manifest_sha256,
            }, pretty=args.pretty)
            return 0
        except (ValueError, OSError, json.JSONDecodeError, FileNotFoundError) as error:
            print(json.dumps({"code":"EVALUATION_SUITE_INVALID","message":str(error)}, ensure_ascii=False), file=sys.stderr)
            return 2
    if args.command == "evaluation-suite-run":
        product_store = SQLiteProductStore(args.product_db)
        product_store.initialize()
        evaluation_store = SQLiteEvaluationStore(args.evaluation_db)
        evaluation_store.initialize()
        recorded = RecordedRunEvaluationService(
            project_root=args.project_root,
            product_store=product_store,
            evaluation_store=evaluation_store,
            artifact_root=args.artifact_root,
            runtime_bindings=AgentRuntimeBindingCatalog(args.project_root),
            artifact_service=ArtifactService(
                product_store=product_store,
                blob_store=LocalFilesystemArtifactBlobStore(args.artifact_root),
            ),
        )
        service = EvaluationSuiteService(
            project_root=args.project_root,
            recorded_run_service=recorded,
            evaluation_store=evaluation_store,
        )
        try:
            result = service.run_suite(
                suite_id=args.suite_id,
                subjects=_parse_suite_subjects(args.subject),
                baseline_id=args.baseline_id,
            )
            _json_print(result, pretty=args.pretty)
            return 0 if result["state"] == "PASSED" and result["comparison_state"] != "REGRESSED" else 1
        except (EvaluationSuiteError, ValueError) as error:
            code = error.code.value if isinstance(error, EvaluationSuiteError) else "SUBJECTS_INVALID"
            message = error.message if isinstance(error, EvaluationSuiteError) else str(error)
            print(json.dumps({"code":code,"message":message}, ensure_ascii=False), file=sys.stderr)
            return 2
    if args.command == "evaluation-suite-run-show":
        store = SQLiteEvaluationStore(args.evaluation_db)
        store.initialize()
        try:
            _json_print(store.get_suite_run(args.suite_run_id), pretty=args.pretty)
            return 0
        except KeyError:
            print(json.dumps({"code":"SUITE_RUN_NOT_FOUND","message":"Evaluation Suite run was not found"}), file=sys.stderr)
            return 2
    if args.command == "evaluation-baseline-create":
        product_store = SQLiteProductStore(args.product_db)
        product_store.initialize()
        evaluation_store = SQLiteEvaluationStore(args.evaluation_db)
        evaluation_store.initialize()
        recorded = RecordedRunEvaluationService(
            project_root=args.project_root,
            product_store=product_store,
            evaluation_store=evaluation_store,
            artifact_root=args.artifact_root,
            runtime_bindings=AgentRuntimeBindingCatalog(args.project_root),
            artifact_service=ArtifactService(
                product_store=product_store,
                blob_store=LocalFilesystemArtifactBlobStore(args.artifact_root),
            ),
        )
        service = EvaluationSuiteService(
            project_root=args.project_root,
            recorded_run_service=recorded,
            evaluation_store=evaluation_store,
        )
        try:
            _json_print(service.create_baseline(
                source_suite_run_id=args.source_suite_run_id, label=args.label
            ), pretty=args.pretty)
            return 0
        except EvaluationSuiteError as error:
            print(json.dumps({"code":error.code.value,"message":error.message}, ensure_ascii=False), file=sys.stderr)
            return 2
    if args.command == "evaluation-baseline-show":
        store = SQLiteEvaluationStore(args.evaluation_db)
        store.initialize()
        try:
            _json_print(store.get_baseline(args.baseline_id), pretty=args.pretty)
            return 0
        except KeyError:
            print(json.dumps({"code":"BASELINE_NOT_FOUND","message":"Evaluation Baseline was not found"}), file=sys.stderr)
            return 2
    if args.command == "reference-list":
        try:
            catalog = ReferenceCatalogService(args.project_root)
            _json_print(
                {"references": [item.to_dict() for item in catalog.list_references()]},
                pretty=args.pretty,
            )
            return 0
        except (ReferenceCatalogError, OSError) as error:
            return _reference_error_exit(error)
    if args.command == "reference-verify":
        try:
            catalog = ReferenceCatalogService(args.project_root)
            reference_ids = tuple(args.reference_id) or tuple(
                item.reference_id for item in catalog.list_references()
            )
            results = [catalog.verify_reference(reference_id).to_dict() for reference_id in reference_ids]
            _json_print({"verifications": results}, pretty=args.pretty)
            return 0
        except (ReferenceCatalogError, OSError) as error:
            return _reference_error_exit(error)
    if args.command == "reference-search":
        try:
            catalog = _reference_catalog(args)
            result = catalog.search(
                args.query,
                reference_ids=tuple(args.reference_id) or None,
                max_results=args.max_results,
                max_file_bytes=args.max_file_bytes,
                run_id=args.run_id,
            )
            _json_print(result.to_dict(), pretty=args.pretty)
            return 0
        except (ReferenceCatalogError, ProductStateError, OSError) as error:
            return _reference_error_exit(error)
    if args.command == "reference-read":
        try:
            catalog = _reference_catalog(args)
            result = catalog.read_lines(
                args.reference_id,
                args.path,
                start_line=args.start_line,
                end_line=args.end_line,
                max_lines=args.max_lines,
                max_file_bytes=args.max_file_bytes,
                run_id=args.run_id,
            )
            _json_print(result.to_dict(), pretty=args.pretty)
            return 0
        except (ReferenceCatalogError, ProductStateError, OSError) as error:
            return _reference_error_exit(error)
    return 2
