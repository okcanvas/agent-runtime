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

ADMIN_KEY = "step039-local-admin-key"
SUBMITTER_KEY = "step039-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
ADMIN_HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
SUBMIT_HEADERS = {
    **ADMIN_HEADERS,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY,
}
RAW_REQUEST = "STEP039 native SDK streaming governed request"
IDEMPOTENCY_KEY = "step039-native-sdk-streaming-idempotency-0001"
RAW_TOOL_ARGUMENT_SENTINEL = "STEP039-RAW-TOOL-ARGUMENT-MUST-NOT-LEAK"


def _install_fake_agents() -> tuple[dict[str, int], object, object | None]:
    counters = {"run": 0, "run_streamed": 0}
    previous_agents = sys.modules.get("agents")
    previous_version = importlib.metadata.version
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"

    class FakeAgent:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeRunConfig:
        def __init__(self, **kwargs):
            self.values = kwargs

    class FakeRunHooks:
        pass

    output = CodingAgentResult(
        status=AgentStatus.PARTIAL,
        summary="Native SDK streaming completed through the governed Product path.",
        findings=[],
        unverified=[],
    )
    usage = SimpleNamespace(
        requests=1,
        input_tokens=21,
        output_tokens=9,
        total_tokens=30,
        input_tokens_details=SimpleNamespace(cached_tokens=0),
        output_tokens_details=SimpleNamespace(reasoning_tokens=0),
    )

    class FakeStreamingResult:
        context_wrapper = SimpleNamespace(usage=usage)
        last_response_id = "resp-step039"

        async def stream_events(self):
            agent = self.agent
            hooks = self.hooks
            await hooks.on_agent_start(SimpleNamespace(), agent)
            await hooks.on_llm_start(
                SimpleNamespace(), agent, agent.instructions, [{"role": "user"}]
            )
            yield SimpleNamespace(type="agent_updated_stream_event", new_agent=agent)
            yield SimpleNamespace(
                type="raw_response_event",
                data=SimpleNamespace(type="response.output_text.delta", delta="Native "),
            )
            yield SimpleNamespace(
                type="raw_response_event",
                data=SimpleNamespace(
                    type="response.function_call_arguments.delta",
                    delta=RAW_TOOL_ARGUMENT_SENTINEL,
                ),
            )
            yield SimpleNamespace(
                type="run_item_stream_event",
                name="message_output_created",
                item=SimpleNamespace(
                    type="message_output_item",
                    agent=agent,
                    output=RAW_TOOL_ARGUMENT_SENTINEL,
                ),
            )
            yield SimpleNamespace(
                type="raw_response_event",
                data=SimpleNamespace(type="response.output_text.delta", delta="stream"),
            )
            response = SimpleNamespace(
                response_id="resp-step039", request_id="req-step039", output=[1]
            )
            await hooks.on_llm_end(SimpleNamespace(), agent, response)
            await hooks.on_agent_end(SimpleNamespace(), agent, output)

        def final_output_as(self, output_type, raise_if_incorrect_type=False):
            assert output_type is CodingAgentResult
            assert raise_if_incorrect_type is True
            return output

    class FakeRunner:
        @classmethod
        async def run(cls, *args, **kwargs):
            counters["run"] += 1
            raise AssertionError("STEP039 must use Runner.run_streamed")

        @classmethod
        def run_streamed(cls, agent, request, **kwargs):
            counters["run_streamed"] += 1
            result = FakeStreamingResult()
            result.agent = agent
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
    fake_agents.gen_trace_id = lambda: "trace-step039"
    fake_agents.set_default_openai_key = lambda value: None
    sys.modules["agents"] = fake_agents
    importlib.metadata.version = lambda name: "0.19.0" if name == "openai-agents" else previous_version(name)
    return counters, previous_version, previous_agents


def _restore_fake_agents(previous_version, previous_agents) -> None:
    importlib.metadata.version = previous_version
    if previous_agents is None:
        sys.modules.pop("agents", None)
    else:
        sys.modules["agents"] = previous_agents


def _wait_terminal(client: TestClient, run_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get(f"/v1/runs/{run_id}", headers=ADMIN_HEADERS)
        body = response.json()
        if body.get("status") in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return body
        time.sleep(0.02)
    raise RuntimeError("STEP039 Run did not reach terminal state")


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
                        "id": current.get("id"),
                        "event": current.get("event", "message"),
                        "payload": json.loads(current["data"]),
                    }
                )
            current = {}
            data = []
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


def _counts(database: Path) -> dict[str, int]:
    connection = sqlite3.connect(database)
    try:
        return {
            "tasks": int(connection.execute("SELECT COUNT(*) FROM task").fetchone()[0]),
            "runs": int(connection.execute("SELECT COUNT(*) FROM run").fetchone()[0]),
            "submissions": int(
                connection.execute("SELECT COUNT(*) FROM run_submission_preflight").fetchone()[0]
            ),
            "artifacts": int(connection.execute("SELECT COUNT(*) FROM artifact").fetchone()[0]),
        }
    finally:
        connection.close()


def run_acceptance(output: Path) -> int:
    references_before = {
        item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()
    }
    counters, previous_version, previous_agents = _install_fake_agents()
    previous_api_key = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "step039-hidden-api-key"
    try:
        with AcceptanceWorkspace(step_id="STEP039", output=output) as workspace:
            product_db = workspace.database_dir / "product.sqlite3"
            payload_root = workspace.scratch_dir / "protected-payloads"
            broker = InMemoryNativeSDKStreamBroker()
            app = create_app(
                project_root=ROOT,
                product_db=product_db,
                artifact_root=workspace.artifact_dir,
                admin_key=ADMIN_KEY,
                run_submitter_key=SUBMITTER_KEY,
                protected_payload_root=payload_root,
                protected_payload_key=PAYLOAD_KEY,
                native_stream_broker=broker,
            )
            with TestClient(app) as client:
                unauthenticated = client.get("/v1/runs/unknown/sdk-stream")
                preflight = client.post(
                    "/v1/run-submissions/preflight",
                    headers=SUBMIT_HEADERS,
                    json={
                        "agent_definition_id": "coding-agent",
                        "input": RAW_REQUEST,
                        "model": "deterministic-step039-model",
                        "idempotency_key": IDEMPOTENCY_KEY,
                    },
                ).json()
                confirmed_response = client.post(
                    f"/v1/run-submissions/{preflight['submission_id']}/confirm",
                    headers=SUBMIT_HEADERS,
                    json={"confirmation": preflight["confirmation_challenge"]},
                )
                confirmed = confirmed_response.json()
                terminal = _wait_terminal(client, confirmed["run_id"])
                native_response = client.get(
                    f"/v1/runs/{confirmed['run_id']}/sdk-stream",
                    headers=ADMIN_HEADERS,
                )
                native_events = _parse_sse(native_response.text)
                persisted = client.get(
                    f"/v1/runs/{confirmed['run_id']}/events", headers=ADMIN_HEADERS
                ).json()["events"]
                artifact = client.get(
                    f"/v1/runs/{confirmed['run_id']}/artifact", headers=ADMIN_HEADERS
                ).json()
                submission = client.get(
                    f"/v1/run-submissions/{preflight['submission_id']}",
                    headers=ADMIN_HEADERS,
                ).json()

            references_after = {
                item.reference_id: item.to_dict()
                for item in ReferenceCatalogService(ROOT).verify_all()
            }
            event_types = [str(item["event"]) for item in native_events]
            native_payload_text = json.dumps(native_events, ensure_ascii=False)
            persisted_text = json.dumps(persisted, ensure_ascii=False)
            assembled_text = "".join(
                str(item["payload"]["payload"].get("delta", ""))
                for item in native_events
                if item["event"] == "model.text.delta"
            )
            final_counts = _counts(product_db)
            checks = {
                "native_sdk_runner_used_once": counters["run_streamed"] == 1
                and counters["run"] == 0,
                "run_completed_without_stream_subscriber": terminal.get("status") == "SUCCEEDED",
                "native_stream_auth_required": unauthenticated.status_code == 401,
                "native_stream_endpoint_returned_200": native_response.status_code == 200,
                "native_stream_marked_ephemeral": native_response.headers.get(
                    "x-okcanvas-stream-durability"
                )
                == "ephemeral",
                "native_stream_event_sequence_exact": event_types
                == [
                    "sdk.stream.started",
                    "agent.updated",
                    "model.text.delta",
                    "run.item",
                    "model.text.delta",
                    "sdk.stream.completed",
                ],
                "text_deltas_assembled_exact": assembled_text == "Native stream",
                "agent_update_exposed": any(
                    item["event"] == "agent.updated"
                    and item["payload"]["payload"].get("agent_name")
                    == "OKCanvas Coding Analyst"
                    for item in native_events
                ),
                "run_item_metadata_exposed": any(
                    item["event"] == "run.item"
                    and item["payload"]["payload"].get("item_type")
                    == "message_output_item"
                    for item in native_events
                ),
                "raw_tool_arguments_not_streamed": RAW_TOOL_ARGUMENT_SENTINEL
                not in native_payload_text,
                "native_events_not_persisted": all(
                    not str(item.get("event_type", "")).startswith("sdk.stream")
                    and item.get("event_type") not in {"model.text.delta", "run.item", "agent.updated"}
                    for item in persisted
                ),
                "text_delta_not_persisted": "Native stream" not in persisted_text,
                "canonical_events_preserved": all(
                    required in [item.get("event_type") for item in persisted]
                    for required in (
                        "run.created",
                        "run.started",
                        "agent.started",
                        "model.started",
                        "model.completed",
                        "agent.completed",
                        "artifact.created",
                        "run.completed",
                        "payload.retention.applied",
                    )
                ),
                "artifact_verified": artifact.get("content", {}).get("summary")
                == "Native SDK streaming completed through the governed Product path.",
                "product_counts_exact": final_counts
                == {"tasks": 1, "runs": 1, "submissions": 1, "artifacts": 1},
                "successful_payload_deleted": submission.get("payload_retention_state")
                == "DELETED"
                and len(list(payload_root.glob("payload_*.json"))) == 0,
                "raw_request_not_in_product_db": RAW_REQUEST.encode() not in product_db.read_bytes(),
                "api_key_not_in_product_db": b"step039-hidden-api-key"
                not in product_db.read_bytes(),
                "references_unchanged": references_before == references_after,
                "cleanup_completed": True,
            }
            payload: dict[str, object] = {
                "schema_version": "okcanvas-step039-acceptance-v1",
                "state": "PASSED" if all(checks.values()) else "FAILED",
                "checks": checks,
                "run_id": confirmed.get("run_id"),
                "submission_id": preflight.get("submission_id"),
                "gateway_counts": counters,
                "native_stream": {
                    "event_count": len(native_events),
                    "event_types": event_types,
                    "assembled_text": assembled_text,
                    "durability": native_response.headers.get(
                        "x-okcanvas-stream-durability"
                    ),
                },
                "persisted_event_count": len(persisted),
                "final_counts": final_counts,
                "artifact_id": artifact.get("artifact_id"),
            }
            final = workspace.finalize(payload)
            final["checks"]["cleanup_completed"] = (
                final["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
            )
            final["state"] = "PASSED" if all(final["checks"].values()) else "FAILED"
            output.write_text(json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8")
            print(json.dumps(final, indent=2, ensure_ascii=False))
            return 0 if final["state"] == "PASSED" else 1
    finally:
        _restore_fake_agents(previous_version, previous_agents)
        if previous_api_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = previous_api_key


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP039_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
