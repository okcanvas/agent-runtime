from __future__ import annotations

import argparse
import base64
import importlib.metadata
import json
import os
import sqlite3
import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
from okcanvas_agent_runtime.adapters.streaming import InMemoryNativeSDKStreamBroker

ADMIN_KEY = "step042-local-admin-key"
SUBMITTER_KEY = "step042-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
ADMIN_HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
SUBMIT_HEADERS = {**ADMIN_HEADERS, "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY}
RAW_REQUEST = "STEP042 parent must invoke one declared specialist and retain control."
IDEMPOTENCY_KEY = "step042-agent-as-tool-idempotency-0001"
RAW_ARGUMENT_SENTINEL = "STEP042-RAW-TOOL-ARGUMENT-MUST-NOT-PERSIST"
RAW_RESULT_SENTINEL = "STEP042-RAW-CHILD-ITEM-MUST-NOT-PERSIST"


def _usage(input_tokens: int, output_tokens: int):
    return SimpleNamespace(
        requests=1,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        input_tokens_details=SimpleNamespace(cached_tokens=0),
        output_tokens_details=SimpleNamespace(reasoning_tokens=0),
    )


def _install_fake_agents():
    counters = {
        "run": 0,
        "outer_run_streamed": 0,
        "nested_run_streamed": 0,
        "as_tool_constructed": 0,
        "agent_tool_invoked": 0,
    }
    captured: dict[str, object] = {}
    previous = {"agents": sys.modules.get("agents")}
    previous_version = importlib.metadata.version
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"

    parent_before = _usage(11, 3)
    after_child = _usage(28, 8)
    total_usage = _usage(40, 12)
    child_output = CodingAgentResult(
        status=AgentStatus.PASS,
        summary="Nested specialist returned a bounded structured result.",
        findings=[],
        unverified=[],
    )
    parent_output = CodingAgentResult(
        status=AgentStatus.PASS,
        summary="Parent retained control after the nested specialist returned.",
        findings=[],
        unverified=[],
    )

    class FakeRunConfig:
        def __init__(self, **kwargs):
            self.values = kwargs

    class FakeRunHooks:
        pass

    class FakeAgentTool:
        def __init__(self, child, **kwargs):
            self.child = child
            self.name = kwargs["tool_name"]
            self.description = kwargs["tool_description"]
            self._kwargs = kwargs
            self._tool_origin = SimpleNamespace(
                type=SimpleNamespace(value="agent_as_tool"),
                agent_name=child.name,
                agent_tool_name=self.name,
            )

        async def on_invoke_tool(self, context, input_json):
            counters["agent_tool_invoked"] += 1
            counters["nested_run_streamed"] += 1
            captured["nested_input"] = input_json
            hooks = self._kwargs["hooks"]
            await hooks.on_agent_start(SimpleNamespace(usage=parent_before), self.child)
            await hooks.on_llm_start(
                SimpleNamespace(usage=parent_before),
                self.child,
                self.child.instructions,
                [{"role": "user"}],
            )
            on_stream = self._kwargs["on_stream"]
            await on_stream(
                {
                    "event": SimpleNamespace(
                        type="agent_updated_stream_event", new_agent=self.child
                    ),
                    "agent": self.child,
                    "tool_call": SimpleNamespace(call_id="nested-call"),
                }
            )
            await on_stream(
                {
                    "event": SimpleNamespace(
                        type="raw_response_event",
                        data=SimpleNamespace(
                            type="response.output_text.delta", delta="Nested specialist"
                        ),
                    ),
                    "agent": self.child,
                    "tool_call": SimpleNamespace(call_id="nested-call"),
                }
            )
            await on_stream(
                {
                    "event": SimpleNamespace(
                        type="run_item_stream_event",
                        name="nested_message",
                        item=SimpleNamespace(
                            type="message_output_item",
                            agent=self.child,
                            content=RAW_RESULT_SENTINEL,
                        ),
                    ),
                    "agent": self.child,
                    "tool_call": SimpleNamespace(call_id="nested-call"),
                }
            )
            await hooks.on_llm_end(
                SimpleNamespace(usage=after_child),
                self.child,
                SimpleNamespace(response_id="resp-step042-child", request_id="req-child", output=[1]),
            )
            await hooks.on_agent_end(SimpleNamespace(usage=after_child), self.child, child_output)

            class NestedResult:
                context_wrapper = SimpleNamespace(usage=after_child)
                final_output = child_output
                new_items = []

                def final_output_as(self, output_type, raise_if_incorrect_type=False):
                    assert output_type is CodingAgentResult
                    assert raise_if_incorrect_type is True
                    return child_output

            return await self._kwargs["custom_output_extractor"](NestedResult())

    class FakeAgent:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

        def as_tool(self, **kwargs):
            counters["as_tool_constructed"] += 1
            captured["child_run_config"] = kwargs["run_config"].values
            captured["child_session"] = kwargs["session"]
            captured["child_failure_error_function"] = kwargs["failure_error_function"]
            return FakeAgentTool(self, **kwargs)

    class FakeStreamingResult:
        context_wrapper = SimpleNamespace(usage=total_usage)
        last_response_id = "resp-step042-parent-final"

        async def stream_events(self):
            parent = captured["parent_agent"]
            hooks = captured["outer_hooks"]
            tool = parent.tools[0]
            await hooks.on_agent_start(SimpleNamespace(usage=_usage(0, 0)), parent)
            await hooks.on_llm_start(
                SimpleNamespace(usage=_usage(0, 0)), parent, parent.instructions, [{"role": "user"}]
            )
            await hooks.on_llm_end(
                SimpleNamespace(usage=parent_before),
                parent,
                SimpleNamespace(response_id="resp-parent-before", request_id="req-1", output=[1]),
            )
            tool_context = SimpleNamespace(
                tool_name=tool.name,
                tool_call_id="agent-tool-call-1",
                tool_arguments='{"input":"' + RAW_ARGUMENT_SENTINEL + '"}',
                tool_call=SimpleNamespace(call_id="agent-tool-call-1"),
                usage=parent_before,
                run_config=SimpleNamespace(parent=True),
                context=None,
            )
            await hooks.on_tool_start(tool_context, parent, tool)
            result = await tool.on_invoke_tool(tool_context, tool_context.tool_arguments)
            captured["bounded_child_result"] = result
            tool_context.usage = after_child
            await hooks.on_tool_end(tool_context, parent, tool, result)
            await hooks.on_llm_start(
                SimpleNamespace(usage=after_child), parent, parent.instructions, [{"role": "tool"}]
            )
            await hooks.on_llm_end(
                SimpleNamespace(usage=total_usage),
                parent,
                SimpleNamespace(response_id="resp-parent-final", request_id="req-2", output=[1]),
            )
            await hooks.on_agent_end(SimpleNamespace(usage=total_usage), parent, parent_output)
            yield SimpleNamespace(
                type="raw_response_event",
                data=SimpleNamespace(type="response.output_text.delta", delta="Parent final"),
            )

        def final_output_as(self, output_type, raise_if_incorrect_type=False):
            assert output_type is CodingAgentResult
            assert raise_if_incorrect_type is True
            return parent_output

    class FakeRunner:
        @classmethod
        async def run(cls, *args, **kwargs):
            counters["run"] += 1
            raise AssertionError("STEP042 must use streaming")

        @classmethod
        def run_streamed(cls, agent, request, **kwargs):
            counters["outer_run_streamed"] += 1
            captured["parent_agent"] = agent
            captured["outer_hooks"] = kwargs["hooks"]
            captured["request"] = request
            return FakeStreamingResult()

    class FakeModelSettings:
        def __init__(self, **kwargs):
            self.values = kwargs

    class _Step052FakeModelRetrySettings:
        def __init__(self, **kwargs):
            self.max_retries = kwargs.get("max_retries")
            self.policy = kwargs.get("policy")

    class _Step052FakeRetryPolicies:
        @staticmethod
        def never():
            return lambda _context: False

    fake_agents.Agent = FakeAgent
    fake_agents.ModelSettings = FakeModelSettings
    fake_agents.ModelRetrySettings = _Step052FakeModelRetrySettings
    fake_agents.retry_policies = _Step052FakeRetryPolicies()
    fake_agents.RunConfig = FakeRunConfig
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_agents.ModelSettings = FakeModelSettings
    fake_agents.gen_trace_id = lambda: "trace-step042"
    fake_agents.set_default_openai_key = lambda value: None
    sys.modules["agents"] = fake_agents
    importlib.metadata.version = (
        lambda name: "0.19.0" if name == "openai-agents" else previous_version(name)
    )
    return counters, captured, previous_version, previous


def _restore(previous_version, previous_modules) -> None:
    importlib.metadata.version = previous_version
    for name, module in previous_modules.items():
        if module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module


def _wait_terminal(client: TestClient, run_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        body = client.get(f"/v1/runs/{run_id}", headers=ADMIN_HEADERS).json()
        if body.get("status") in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return body
        time.sleep(0.02)
    raise RuntimeError("STEP042 Run did not reach terminal state")


def _parse_sse(text: str) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    current: dict[str, str] = {}
    data: list[str] = []
    for line in text.splitlines() + [""]:
        if not line:
            if data:
                current["data"] = "\n".join(data)
                result.append(
                    {
                        "event": current.get("event", "message"),
                        "payload": json.loads(current["data"]),
                    }
                )
            current, data = {}, []
            continue
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if field == "data":
            data.append(value)
        elif field in {"id", "event"}:
            current[field] = value
    return result


def _counts(product_db: Path, evaluation_db: Path) -> dict[str, int]:
    product = sqlite3.connect(product_db)
    evaluation = sqlite3.connect(evaluation_db)
    try:
        return {
            "tasks": int(product.execute("SELECT COUNT(*) FROM task").fetchone()[0]),
            "runs": int(product.execute("SELECT COUNT(*) FROM run").fetchone()[0]),
            "submissions": int(product.execute("SELECT COUNT(*) FROM run_submission_preflight").fetchone()[0]),
            "invocations": int(product.execute("SELECT COUNT(*) FROM agent_invocation").fetchone()[0]),
            "events": int(product.execute("SELECT COUNT(*) FROM run_event").fetchone()[0]),
            "artifacts": int(product.execute("SELECT COUNT(*) FROM artifact").fetchone()[0]),
            "evaluations": int(evaluation.execute("SELECT COUNT(*) FROM evaluation_result").fetchone()[0]),
        }
    finally:
        product.close()
        evaluation.close()


def run_acceptance(output: Path) -> int:
    references_before = {
        item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()
    }
    counters, captured, previous_version, previous_modules = _install_fake_agents()
    previous_key = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "step042-hidden-api-key"
    try:
        with AcceptanceWorkspace(step_id="STEP042", output=output) as workspace:
            product_db = workspace.database_dir / "product.sqlite3"
            evaluation_db = workspace.database_dir / "evaluation.sqlite3"
            payload_root = workspace.scratch_dir / "protected-payloads"
            broker = InMemoryNativeSDKStreamBroker()
            app = create_app(
                project_root=ROOT,
                product_db=product_db,
                artifact_root=workspace.artifact_dir,
                evaluation_db=evaluation_db,
                admin_key=ADMIN_KEY,
                run_submitter_key=SUBMITTER_KEY,
                protected_payload_root=payload_root,
                protected_payload_key=PAYLOAD_KEY,
                native_stream_broker=broker,
            )
            with TestClient(app) as client:
                preflight_response = client.post(
                    "/v1/run-submissions/preflight",
                    headers=SUBMIT_HEADERS,
                    json={
                        "agent_definition_id": "agent-tool-manager-agent",
                        "input": RAW_REQUEST,
                        "model": "deterministic-step042-model",
                        "idempotency_key": IDEMPOTENCY_KEY,
                    },
                )
                preflight = preflight_response.json()
                confirm_response = client.post(
                    f"/v1/run-submissions/{preflight['submission_id']}/confirm",
                    headers=SUBMIT_HEADERS,
                    json={"confirmation": preflight["confirmation_challenge"]},
                )
                confirmed = confirm_response.json()
                terminal = _wait_terminal(client, confirmed["run_id"])
                invocations = client.get(
                    f"/v1/runs/{confirmed['run_id']}/invocations", headers=ADMIN_HEADERS
                ).json()["invocations"]
                events = client.get(
                    f"/v1/runs/{confirmed['run_id']}/events", headers=ADMIN_HEADERS
                ).json()["events"]
                native_response = client.get(
                    f"/v1/runs/{confirmed['run_id']}/sdk-stream", headers=ADMIN_HEADERS
                )
                native_events = _parse_sse(native_response.text)
                artifact = client.get(
                    f"/v1/runs/{confirmed['run_id']}/artifact", headers=ADMIN_HEADERS
                ).json()
                evaluation_response = client.post(
                    f"/v1/runs/{confirmed['run_id']}/evaluations",
                    headers=ADMIN_HEADERS,
                    json={"case_id": "agent-as-tool-v1"},
                )
                evaluation = evaluation_response.json()
                submission = client.get(
                    f"/v1/run-submissions/{preflight['submission_id']}", headers=ADMIN_HEADERS
                ).json()

            references_after = {
                item.reference_id: item.to_dict()
                for item in ReferenceCatalogService(ROOT).verify_all()
            }
            root = next(item for item in invocations if item["invocation_kind"] == "ROOT")
            child = next(
                item for item in invocations if item["invocation_kind"] == "AGENT_AS_TOOL"
            )
            started = [item for item in events if item["event_type"] == "agent.tool.started"]
            completed = [item for item in events if item["event_type"] == "agent.tool.completed"]
            started_payload = started[0]["payload"] if started else {}
            completed_payload = completed[0]["payload"] if completed else {}
            product_text = product_db.read_bytes().decode("utf-8", errors="ignore")
            native_text = json.dumps(native_events, ensure_ascii=False)
            final_counts = _counts(product_db, evaluation_db)
            bounded_result = str(captured.get("bounded_child_result", ""))
            child_run_config = captured.get("child_run_config", {})
            checks = {
                "agent_tool_preflight_executable": preflight_response.status_code == 201
                and preflight.get("execution_mode") == "IMMEDIATE_AFTER_CONFIRMATION"
                and preflight.get("executable_now") is True,
                "agent_as_tool_constructed_once": counters["as_tool_constructed"] == 1,
                "outer_and_nested_streaming_exact": counters["outer_run_streamed"] == 1
                and counters["nested_run_streamed"] == 1
                and counters["run"] == 0,
                "agent_tool_invoked_once": counters["agent_tool_invoked"] == 1,
                "one_product_task_and_run": terminal.get("status") == "SUCCEEDED"
                and final_counts["tasks"] == 1
                and final_counts["runs"] == 1
                and final_counts["submissions"] == 1,
                "exactly_two_invocations": final_counts["invocations"] == 2,
                "root_invocation_succeeded": root["state"] == "SUCCEEDED"
                and root["agent_definition_id"] == "agent-tool-manager-agent",
                "child_invocation_succeeded": child["state"] == "SUCCEEDED"
                and child["agent_definition_id"] == "agent-tool-specialist-agent",
                "child_relationship_exact": child["parent_invocation_id"] == root["invocation_id"]
                and child["root_invocation_id"] == root["invocation_id"]
                and child["depth"] == 1
                and child["ordinal"] == 1,
                "invocation_namespaces_distinct": root["state_namespace"] != child["state_namespace"],
                "parent_control_retained": completed_payload.get("parent_control_retained") is True
                and root["completed_at"] >= child["completed_at"],
                "parent_usage_partition_exact": (
                    root["input_tokens"], root["output_tokens"], root["total_tokens"]
                ) == (23, 7, 30),
                "child_usage_partition_exact": (
                    child["input_tokens"], child["output_tokens"], child["total_tokens"]
                ) == (17, 5, 22),
                "run_usage_total_exact": (
                    terminal.get("input_tokens"), terminal.get("output_tokens"), terminal.get("total_tokens")
                ) == (40, 12, 52),
                "canonical_agent_tool_events_exact": len(started) == 1
                and len(completed) == 1
                and started_payload.get("from_invocation_id") == root["invocation_id"]
                and started_payload.get("to_invocation_id") == child["invocation_id"]
                and completed_payload.get("to_invocation_id") == child["invocation_id"],
                "agent_tool_policy_exact": started_payload.get("input_mode") == "MODEL_GENERATED_TEXT"
                and started_payload.get("output_mode") == "BOUNDED_STRUCTURED_JSON"
                and started_payload.get("run_config_inherited") is False,
                "child_run_config_explicit": isinstance(child_run_config, dict)
                and child_run_config.get("trace_metadata", {}).get("run_config_inherited") is False
                and captured.get("child_session") is None
                and captured.get("child_failure_error_function") is None,
                "bounded_structured_child_result": bounded_result.startswith("{")
                and len(bounded_result.encode("utf-8")) <= 8192
                and "Nested specialist" in bounded_result,
                "safe_nested_stream_metadata": any(
                    item["event"] == "agent.tool.agent.updated"
                    and item["payload"]["payload"].get("agent_id")
                    == "agent-tool-specialist-agent"
                    for item in native_events
                )
                and any(item["event"] == "agent.tool.model.text.delta" for item in native_events)
                and any(item["event"] == "agent.tool.stream.completed" for item in native_events),
                "raw_nested_data_not_streamed": RAW_ARGUMENT_SENTINEL not in native_text
                and RAW_RESULT_SENTINEL not in native_text,
                "raw_nested_data_not_persisted": RAW_ARGUMENT_SENTINEL not in product_text
                and RAW_RESULT_SENTINEL not in product_text,
                "language_agents_have_no_workspace": root["workspace_access"] == "none"
                and root["workspace_ref"] is None
                and child["workspace_access"] == "none"
                and child["workspace_ref"] is None,
                "artifact_verified": artifact.get("artifact_id")
                and artifact.get("sha256")
                and artifact.get("content", {}).get("status") == "PASS",
                "recorded_evaluation_passed": evaluation_response.status_code == 201
                and evaluation.get("state") == "PASSED",
                "successful_payload_deleted": submission.get("payload_retention_state") == "DELETED"
                and list(payload_root.glob("*.payload")) == [],
                "product_counts_exact": final_counts
                == {
                    "tasks": 1,
                    "runs": 1,
                    "submissions": 1,
                    "invocations": 2,
                    "events": len(events),
                    "artifacts": 1,
                    "evaluations": 1,
                },
                "raw_request_and_keys_not_in_product_db": RAW_REQUEST not in product_text
                and "step042-hidden-api-key" not in product_text,
                "references_unchanged": references_before == references_after,
                "cleanup_completed": True,
            }
            report = {
                "schema_version": "okcanvas-step042-acceptance-v1",
                "state": "PASSED" if all(checks.values()) else "FAILED",
                "checks": checks,
                "run_id": confirmed["run_id"],
                "submission_id": preflight["submission_id"],
                "runtime_binding_sha256": preflight.get("runtime_binding_sha256"),
                "gateway_counts": counters,
                "invocations": {"root": root, "agent_as_tool": child},
                "agent_tool_events": {
                    "started": started_payload,
                    "completed": completed_payload,
                },
                "native_stream": {
                    "event_count": len(native_events),
                    "event_types": [item["event"] for item in native_events],
                    "durability": native_response.headers.get("X-OKCanvas-Stream-Durability"),
                },
                "final_counts": final_counts,
                "artifact_id": artifact.get("artifact_id"),
                "evaluation_id": evaluation.get("evaluation_id"),
            }
            final_report = workspace.finalize(report)
            final_report["checks"]["cleanup_completed"] = (
                final_report["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
            )
            final_report["state"] = (
                "PASSED" if all(final_report["checks"].values()) else "FAILED"
            )
            output.write_text(
                json.dumps(final_report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(json.dumps(final_report, ensure_ascii=False, indent=2))
            return 0 if final_report["state"] == "PASSED" else 1
    finally:
        if previous_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = previous_key
        _restore(previous_version, previous_modules)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=ROOT / "docs" / "evidence" / "STEP042_ACCEPTANCE.json"
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
