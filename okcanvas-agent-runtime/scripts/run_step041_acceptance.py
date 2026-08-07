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

ADMIN_KEY = "step041-local-admin-key"
SUBMITTER_KEY = "step041-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
ADMIN_HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
SUBMIT_HEADERS = {**ADMIN_HEADERS, "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY}
RAW_REQUEST = "STEP041 governed request must transfer once to the declared specialist."
IDEMPOTENCY_KEY = "step041-native-handoff-idempotency-0001"
RAW_HISTORY_SENTINEL = "STEP041-RAW-HISTORY-MUST-NOT-PERSIST"


def _install_fake_agents():
    counters = {"run": 0, "run_streamed": 0, "handoff_constructed": 0}
    previous = {
        name: sys.modules.get(name)
        for name in ("agents", "agents.extensions", "agents.extensions.handoff_filters")
    }
    previous_version = importlib.metadata.version
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"
    extensions = types.ModuleType("agents.extensions")
    filters = types.ModuleType("agents.extensions.handoff_filters")

    def remove_all_tools(data):
        return data

    filters.remove_all_tools = remove_all_tools
    extensions.handoff_filters = filters

    class FakeAgent:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeHandoff:
        def __init__(self, agent, **kwargs):
            self.agent = agent
            for key, value in kwargs.items():
                setattr(self, key, value)

    def fake_handoff(agent, **kwargs):
        counters["handoff_constructed"] += 1
        return FakeHandoff(agent, **kwargs)

    class FakeRunConfig:
        def __init__(self, **kwargs):
            self.values = kwargs

    class FakeRunHooks:
        pass

    parent_usage = SimpleNamespace(
        requests=1,
        input_tokens=12,
        output_tokens=4,
        total_tokens=16,
        input_tokens_details=SimpleNamespace(cached_tokens=0),
        output_tokens_details=SimpleNamespace(reasoning_tokens=0),
    )
    total_usage = SimpleNamespace(
        requests=2,
        input_tokens=30,
        output_tokens=10,
        total_tokens=40,
        input_tokens_details=SimpleNamespace(cached_tokens=0),
        output_tokens_details=SimpleNamespace(reasoning_tokens=0),
    )
    output = CodingAgentResult(
        status=AgentStatus.PASS,
        summary="Native Handoff completed through one governed Product Run.",
        findings=[],
        unverified=[],
    )

    class FakeStreamingResult:
        context_wrapper = SimpleNamespace(usage=total_usage)
        last_response_id = "resp-step041-child"

        async def stream_events(self):
            root = self.root
            child = root.handoffs[0].agent
            hooks = self.hooks
            await hooks.on_agent_start(SimpleNamespace(usage=SimpleNamespace()), root)
            await hooks.on_llm_start(SimpleNamespace(), root, root.instructions, [{"role": "user"}])
            await hooks.on_llm_end(
                SimpleNamespace(usage=parent_usage),
                root,
                SimpleNamespace(response_id="resp-step041-root", request_id="req-root", output=[1]),
            )
            await hooks.on_handoff(SimpleNamespace(usage=parent_usage), root, child)
            yield SimpleNamespace(type="agent_updated_stream_event", new_agent=child)
            await hooks.on_agent_start(SimpleNamespace(usage=total_usage), child)
            await hooks.on_llm_start(SimpleNamespace(), child, child.instructions, [{"role": "user"}])
            yield SimpleNamespace(
                type="raw_response_event",
                data=SimpleNamespace(type="response.output_text.delta", delta="Specialist result"),
            )
            yield SimpleNamespace(
                type="run_item_stream_event",
                name="handoff_output_item",
                item=SimpleNamespace(
                    type="handoff_output_item",
                    agent=child,
                    output=RAW_HISTORY_SENTINEL,
                ),
            )
            await hooks.on_llm_end(
                SimpleNamespace(usage=total_usage),
                child,
                SimpleNamespace(response_id="resp-step041-child", request_id="req-child", output=[1]),
            )
            await hooks.on_agent_end(SimpleNamespace(usage=total_usage), child, output)

        def final_output_as(self, output_type, raise_if_incorrect_type=False):
            assert output_type is CodingAgentResult
            assert raise_if_incorrect_type is True
            return output

    class FakeRunner:
        @classmethod
        async def run(cls, *args, **kwargs):
            counters["run"] += 1
            raise AssertionError("STEP041 must use Runner.run_streamed")

        @classmethod
        def run_streamed(cls, agent, request, **kwargs):
            counters["run_streamed"] += 1
            result = FakeStreamingResult()
            result.root = agent
            result.hooks = kwargs["hooks"]
            return result

    class _Step052FakeModelRetrySettings:
        def __init__(self, **kwargs):
            self.max_retries = kwargs.get("max_retries")
            self.policy = kwargs.get("policy")

    class _Step052FakeRetryPolicies:
        @staticmethod
        def never():
            return lambda _context: False

    class FakeModelSettings:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    fake_agents.Agent = FakeAgent
    fake_agents.ModelSettings = FakeModelSettings
    fake_agents.ModelRetrySettings = _Step052FakeModelRetrySettings
    fake_agents.retry_policies = _Step052FakeRetryPolicies()
    fake_agents.RunConfig = FakeRunConfig
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_agents.handoff = fake_handoff
    fake_agents.gen_trace_id = lambda: "trace-step041"
    fake_agents.set_default_openai_key = lambda value: None
    sys.modules["agents"] = fake_agents
    sys.modules["agents.extensions"] = extensions
    sys.modules["agents.extensions.handoff_filters"] = filters
    importlib.metadata.version = (
        lambda name: "0.19.0" if name == "openai-agents" else previous_version(name)
    )
    return counters, previous_version, previous


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
    raise RuntimeError("STEP041 Run did not reach terminal state")


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
    counters, previous_version, previous_modules = _install_fake_agents()
    previous_key = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "step041-hidden-api-key"
    try:
        with AcceptanceWorkspace(step_id="STEP041", output=output) as workspace:
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
                        "agent_definition_id": "handoff-triage-agent",
                        "input": RAW_REQUEST,
                        "model": "deterministic-step041-model",
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
                invocations_response = client.get(
                    f"/v1/runs/{confirmed['run_id']}/invocations", headers=ADMIN_HEADERS
                )
                invocations = invocations_response.json()["invocations"]
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
                    json={"case_id": "native-handoff-v1"},
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
            child = next(item for item in invocations if item["invocation_kind"] == "HANDOFF")
            handoff_events = [item for item in events if item["event_type"] == "agent.handoff"]
            handoff_payload = handoff_events[0]["payload"] if handoff_events else {}
            native_payload_text = json.dumps(native_events, ensure_ascii=False)
            product_bytes = product_db.read_bytes()
            final_counts = _counts(product_db, evaluation_db)
            checks = {
                "native_handoff_preflight_executable": preflight_response.status_code == 201
                and preflight.get("execution_mode") == "IMMEDIATE_AFTER_CONFIRMATION"
                and preflight.get("executable_now") is True,
                "native_handoff_sdk_constructed_once": counters["handoff_constructed"] == 1,
                "native_streaming_runner_used_once": counters["run_streamed"] == 1
                and counters["run"] == 0,
                "one_product_task_and_run": terminal.get("status") == "SUCCEEDED"
                and final_counts["tasks"] == 1
                and final_counts["runs"] == 1
                and final_counts["submissions"] == 1,
                "exactly_two_invocations": final_counts["invocations"] == 2,
                "root_invocation_succeeded": root["state"] == "SUCCEEDED"
                and root["agent_definition_id"] == "handoff-triage-agent",
                "child_invocation_succeeded": child["state"] == "SUCCEEDED"
                and child["agent_definition_id"] == "handoff-specialist-agent",
                "child_relationship_exact": child["parent_invocation_id"] == root["invocation_id"]
                and child["root_invocation_id"] == root["invocation_id"]
                and child["depth"] == 1
                and child["ordinal"] == 1,
                "invocation_namespaces_distinct": root["state_namespace"] != child["state_namespace"],
                "parent_usage_partition_exact": (root["input_tokens"], root["output_tokens"], root["total_tokens"])
                == (12, 4, 16),
                "child_usage_partition_exact": (child["input_tokens"], child["output_tokens"], child["total_tokens"])
                == (18, 6, 24),
                "run_usage_total_exact": (terminal.get("input_tokens"), terminal.get("output_tokens"), terminal.get("total_tokens"))
                == (30, 10, 40),
                "canonical_handoff_event_exact": len(handoff_events) == 1
                and handoff_payload.get("from_invocation_id") == root["invocation_id"]
                and handoff_payload.get("to_invocation_id") == child["invocation_id"]
                and handoff_payload.get("from_agent_id") == "handoff-triage-agent"
                and handoff_payload.get("to_agent_id") == "handoff-specialist-agent",
                "handoff_filter_policy_exact": handoff_payload.get("input_filter_mode") == "REMOVE_ALL_TOOLS"
                and handoff_payload.get("nest_handoff_history") is False
                and handoff_payload.get("handoff_input_payload_enabled") is False,
                "handoff_raw_history_not_persisted": RAW_HISTORY_SENTINEL not in product_bytes.decode("utf-8", errors="ignore")
                and handoff_payload.get("history_persisted") is False,
                "native_stream_agent_change_safe": any(
                    item["event"] == "agent.updated"
                    and item["payload"]["payload"].get("agent_id") == "handoff-specialist-agent"
                    for item in native_events
                )
                and RAW_HISTORY_SENTINEL not in native_payload_text,
                "language_agents_have_no_workspace": root["workspace_access"] == "none"
                and root["workspace_ref"] is None
                and child["workspace_access"] == "none"
                and child["workspace_ref"] is None,
                "artifact_verified": artifact.get("content", {}).get("status") == "PASS"
                and artifact.get("content", {}).get("summary")
                == "Native Handoff completed through one governed Product Run.",
                "recorded_evaluation_passed": evaluation_response.status_code == 201
                and evaluation.get("state") == "PASSED"
                and evaluation.get("case_id") == "native-handoff-v1",
                "successful_payload_deleted": submission.get("payload_retention_state") == "DELETED"
                and len(list(payload_root.glob("payload_*.json"))) == 0,
                "product_counts_exact": final_counts
                == {"tasks": 1, "runs": 1, "submissions": 1, "invocations": 2, "events": 14, "artifacts": 1, "evaluations": 1},
                "raw_request_and_keys_not_in_product_db": RAW_REQUEST.encode() not in product_bytes
                and ADMIN_KEY.encode() not in product_bytes
                and SUBMITTER_KEY.encode() not in product_bytes
                and b"step041-hidden-api-key" not in product_bytes,
                "references_unchanged": references_before == references_after,
                "cleanup_completed": True,
            }
            payload = {
                "schema_version": "okcanvas-step041-acceptance-v1",
                "state": "PASSED" if all(checks.values()) else "FAILED",
                "checks": checks,
                "run_id": confirmed["run_id"],
                "submission_id": preflight["submission_id"],
                "runtime_binding_sha256": preflight.get("runtime_binding_sha256"),
                "gateway_counts": counters,
                "invocations": {"root": root, "handoff": child},
                "handoff_event": handoff_payload,
                "native_stream": {
                    "event_count": len(native_events),
                    "event_types": [item["event"] for item in native_events],
                    "durability": native_response.headers.get("x-okcanvas-stream-durability"),
                },
                "final_counts": final_counts,
                "artifact_id": artifact.get("artifact_id"),
                "evaluation_id": evaluation.get("evaluation_id"),
            }
            final = workspace.finalize(payload)
            final["checks"]["cleanup_completed"] = (
                final["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
            )
            final["state"] = "PASSED" if all(final["checks"].values()) else "FAILED"
            output.write_text(
                json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print(json.dumps(final, ensure_ascii=False, indent=2))
            return 0 if final["state"] == "PASSED" else 1
    finally:
        _restore(previous_version, previous_modules)
        if previous_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = previous_key


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP041_ACCEPTANCE.json",
    )
    return run_acceptance(parser.parse_args().output)


if __name__ == "__main__":
    raise SystemExit(main())
