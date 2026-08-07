from __future__ import annotations

import json

import httpx
import pytest

from okcanvas_agent_clients.operator import (
    ApprovalOperatorConfig,
    ApprovalOperatorError,
    LocalApprovalOperatorClient,
    decision_confirmation_challenge,
)

ADMIN = "operator-admin-key-123456"
SUBMITTER = "operator-submitter-key-123456"
APPROVAL_ID = "approval_abc123"
RUN_ID = "run_def456"


def _set_keys(monkeypatch) -> None:
    monkeypatch.setenv("OKCANVAS_CONTROL_ADMIN_KEY", ADMIN)
    monkeypatch.setenv("OKCANVAS_RUN_SUBMITTER_KEY", SUBMITTER)


def test_operator_config_forbids_remote_control_api(monkeypatch) -> None:
    _set_keys(monkeypatch)
    with pytest.raises(ApprovalOperatorError) as error:
        ApprovalOperatorConfig.from_env(
            base_url_override="https://example.com:8765",
            require_submitter=True,
        )
    assert error.value.code == "APPROVAL_OPERATOR_REMOTE_URL_FORBIDDEN"


def test_operator_list_uses_admin_authority_and_adds_exact_challenges(monkeypatch) -> None:
    _set_keys(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/tool-approvals"
        assert request.headers["X-OKCanvas-Admin-Key"] == ADMIN
        assert "X-OKCanvas-Run-Submitter-Key" not in request.headers
        return httpx.Response(
            200,
            json={
                "schema_version": "okcanvas-control-tool-approval-list-v1",
                "total": 1,
                "limit": 20,
                "offset": 0,
                "approvals": [
                    {
                        "approval_id": APPROVAL_ID,
                        "submission_id": "submission_1",
                        "task_id": "task_1",
                        "run_id": RUN_ID,
                        "state": "PENDING",
                        "decision": None,
                        "tool_name": "local_text_metrics",
                        "trace_id": None,
                        "tool_execution_count": 0,
                        "created_at": "2026-07-29T00:00:00Z",
                        "decided_at": None,
                        "completed_at": None,
                    }
                ],
            },
        )

    config = ApprovalOperatorConfig.from_env(require_submitter=False)
    with LocalApprovalOperatorClient(config, transport=httpx.MockTransport(handler)) as client:
        result = client.list_approvals()
    item = result["approvals"][0]
    assert item["approve_confirmation"] == f"APPROVE {APPROVAL_ID} {RUN_ID}"
    assert item["reject_confirmation"] == f"REJECT {APPROVAL_ID} {RUN_ID}"
    assert "run_state_ref" not in item


def test_operator_decision_requires_exact_confirmation_before_post(monkeypatch) -> None:
    _set_keys(monkeypatch)
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(f"{request.method} {request.url.path}")
        if request.method == "GET":
            assert request.url.path == f"/v1/tool-approvals/{APPROVAL_ID}/inbox"
            return httpx.Response(
                200,
                json={
                    "approval_id": APPROVAL_ID,
                    "submission_id": "submission_1",
                    "task_id": "task_1",
                    "run_id": RUN_ID,
                    "state": "PENDING",
                    "decision": None,
                    "tool_name": "local_text_metrics",
                    "trace_id": None,
                    "tool_execution_count": 0,
                    "created_at": "2026-07-29T00:00:00Z",
                    "decided_at": None,
                    "completed_at": None,
                },
            )
        raise AssertionError("POST must not occur with a wrong confirmation")

    config = ApprovalOperatorConfig.from_env(require_submitter=True)
    with LocalApprovalOperatorClient(config, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ApprovalOperatorError) as error:
            client.decide(
                approval_id=APPROVAL_ID,
                decision="APPROVE",
                confirmation="APPROVE wrong",
            )
    assert error.value.code == "TOOL_APPROVAL_CONFIRMATION_MISMATCH"
    assert requests == [f"GET /v1/tool-approvals/{APPROVAL_ID}/inbox"]


def test_operator_decision_sends_two_authorities_and_safe_body(monkeypatch) -> None:
    _set_keys(monkeypatch)
    confirmation = decision_confirmation_challenge(
        approval_id=APPROVAL_ID,
        run_id=RUN_ID,
        decision="REJECT",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "approval_id": APPROVAL_ID,
                    "submission_id": "submission_1",
                    "task_id": "task_1",
                    "run_id": RUN_ID,
                    "state": "PENDING",
                    "decision": None,
                    "tool_name": "local_text_metrics",
                    "trace_id": None,
                    "tool_execution_count": 0,
                    "created_at": "2026-07-29T00:00:00Z",
                    "decided_at": None,
                    "completed_at": None,
                },
            )
        assert request.method == "POST"
        assert request.url.path == f"/v1/tool-approvals/{APPROVAL_ID}/decision"
        assert request.headers["X-OKCanvas-Admin-Key"] == ADMIN
        assert request.headers["X-OKCanvas-Run-Submitter-Key"] == SUBMITTER
        assert json.loads(request.content) == {
            "decision": "REJECT",
            "confirmation": confirmation,
        }
        return httpx.Response(
            200,
            json={
                "schema_version": "okcanvas-control-tool-approval-resume-v1",
                "state": "CANCELLED",
                "tool_executed": False,
            },
        )

    config = ApprovalOperatorConfig.from_env(require_submitter=True)
    with LocalApprovalOperatorClient(config, transport=httpx.MockTransport(handler)) as client:
        result = client.decide(
            approval_id=APPROVAL_ID,
            decision="reject",
            confirmation=confirmation,
        )
    assert result["state"] == "CANCELLED"
    assert result["tool_executed"] is False
