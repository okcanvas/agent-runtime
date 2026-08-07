from __future__ import annotations

import json

import httpx
import pytest

from okcanvas_agent_clients.tui import (
    GovernedTUIFlow,
    LocalTUIControlClient,
    TUIClientConfig,
    TUIClientError,
    compatible_agents,
)


ADMIN = "tui-flow-admin-key"
SUBMITTER = "tui-flow-submitter-key"


def _agent(*, tools: list[str] | None = None) -> dict[str, object]:
    return {
        "schema_version": "okcanvas-control-agent-definition-detail-v1",
        "agent_id": "coding-agent",
        "version": "1.0.0",
        "name": "Coding Agent",
        "output_contract": "CodingAgentResult",
        "tools": tools or [],
        "tool_capabilities": [],
        "mcp_servers": [],
        "handoffs": [],
        "agent_tools": [],
        "guardrails": [],
        "guardrail_capabilities": [],
        "workspace_access": "none",
        "max_turns": 2,
        "workflow_name": "coding-agent",
        "session_mode": "disabled",
        "definition_sha256": "a" * 64,
        "instructions_sha256": "b" * 64,
        "instructions_byte_length": 10,
        "output_schema": {"type": "object"},
    }


def _config() -> TUIClientConfig:
    return TUIClientConfig(
        base_url="http://127.0.0.1:8765",
        admin_key=ADMIN,
        submitter_key=SUBMITTER,
    )


def test_compatible_agents_excludes_tool_session_workspace_and_child_graphs() -> None:
    clean = dict(_agent())
    tool = dict(_agent(tools=["local_text_metrics"]), agent_id="tool-agent")
    session = dict(_agent(), agent_id="session-agent", session_mode="sqlite-v1")
    workspace = dict(_agent(), agent_id="workspace-agent", workspace_access="read-only")
    child = dict(_agent(), agent_id="handoff-agent", handoffs=["child-agent"])
    assert [item["agent_id"] for item in compatible_agents([tool, session, clean, workspace, child])] == [
        "coding-agent"
    ]


def test_wrong_confirmation_is_rejected_before_confirm_endpoint() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path == "/v1/agent-definitions/coding-agent":
            return httpx.Response(200, json=_agent())
        if request.url.path == "/v1/run-submissions/preflight":
            return httpx.Response(
                201,
                json={
                    "submission_id": "submission_1",
                    "confirmation_challenge": "RUN coding-agent@1.0.0 abcdef123456",
                    "approval_required": False,
                    "executable_now": True,
                },
            )
        raise AssertionError(request.url)

    with LocalTUIControlClient(_config(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TUIClientError) as caught:
            GovernedTUIFlow(client).execute(
                agent_id="coding-agent",
                request="check this",
                model="test-model",
                evaluation_case_id="tui-client-foundation-v1",
                confirmation_provider=lambda challenge: f"{challenge}-wrong",
            )
    assert caught.value.code == "TUI_CONFIRMATION_MISMATCH"
    assert not any("/confirm" in call for call in calls)


def test_flow_uses_governed_submission_persisted_sse_artifact_and_evaluation() -> None:
    calls: list[str] = []
    event_rows = [
        {"run_id": "run_1", "sequence": 1, "event_type": "run.created", "payload": {}},
        {"run_id": "run_1", "sequence": 2, "event_type": "run.completed", "payload": {}},
    ]
    sse = "".join(
        f"id: {item['sequence']}\nevent: {item['event_type']}\ndata: {json.dumps(item)}\n\n"
        for item in event_rows
    )

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        path = request.url.path
        if path == "/v1/agent-definitions/coding-agent":
            return httpx.Response(200, json=_agent())
        if path == "/v1/run-submissions/preflight":
            assert request.headers["X-OKCanvas-Run-Submitter-Key"] == SUBMITTER
            return httpx.Response(
                201,
                json={
                    "submission_id": "submission_1",
                    "confirmation_challenge": "RUN coding-agent@1.0.0 abcdef123456",
                    "approval_required": False,
                    "executable_now": True,
                    "runtime_binding_sha256": "c" * 64,
                },
            )
        if path == "/v1/run-submissions/submission_1/confirm":
            return httpx.Response(
                202,
                json={
                    "submission": {"submission_id": "submission_1"},
                    "task_id": "task_1",
                    "run_id": "run_1",
                    "scheduled": True,
                    "replayed": False,
                },
            )
        if path == "/v1/runs/run_1/events/stream":
            return httpx.Response(
                200,
                headers={"Content-Type": "text/event-stream"},
                content=sse.encode(),
            )
        if path == "/v1/runs/run_1":
            return httpx.Response(200, json={"run_id": "run_1", "status": "SUCCEEDED"})
        if path == "/v1/runs/run_1/invocations":
            return httpx.Response(
                200,
                json={"invocations": [{"invocation_kind": "ROOT", "state": "SUCCEEDED"}]},
            )
        if path == "/v1/runs/run_1/artifact":
            return httpx.Response(
                200,
                json={"artifact_id": "artifact_1", "content": {"status": "PASS"}},
            )
        if path == "/v1/runs/run_1/evaluations":
            return httpx.Response(
                201,
                json={
                    "evaluation_id": "eval_1",
                    "case_id": "tui-client-foundation-v1",
                    "state": "PASSED",
                    "checks": {"execution_succeeded": True},
                },
            )
        raise AssertionError(request.url)

    seen: list[str] = []
    with LocalTUIControlClient(_config(), transport=httpx.MockTransport(handler)) as client:
        outcome = GovernedTUIFlow(client).execute(
            agent_id="coding-agent",
            request="check this",
            model="test-model",
            evaluation_case_id="tui-client-foundation-v1",
            confirmation_provider=lambda challenge: challenge,
            on_event=lambda event: seen.append(str(event["event_type"])),
        )
    assert outcome.run["status"] == "SUCCEEDED"
    assert outcome.artifact["content"]["status"] == "PASS"
    assert outcome.evaluation["state"] == "PASSED"
    assert seen == ["run.created", "run.completed"]
    assert any("/events/stream" in call for call in calls)
