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
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
from okcanvas_agent_runtime.domain.sessions import SessionBusyError
from okcanvas_agent_runtime.adapters.streaming import InMemoryNativeSDKStreamBroker

ADMIN_KEY = "step043-local-admin-key"
SUBMITTER_KEY = "step043-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SESSION_HISTORY_KEY = base64.urlsafe_b64encode(
    bytes((index + 67) % 256 for index in range(32))
).decode("ascii")
ADMIN_HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
SUBMIT_HEADERS = {**ADMIN_HEADERS, "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY}
TURN1_REQUEST = "Remember that the project code is ORBIT-7."
TURN2_REQUEST = "What is the project code from the previous turn?"
RAW_SENTINEL = "ORBIT-7"
HIDDEN_API_KEY = "step043-hidden-api-key"


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
    counters = {"run": 0, "run_streamed": 0, "session_instances": 0, "session_closes": 0}
    captured: dict[str, object] = {"history_before": [], "session_ids": []}
    previous_agents = sys.modules.get("agents")
    previous_version = importlib.metadata.version
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"

    class FakeSQLiteSession:
        def __init__(self, session_id: str, db_path: str | Path) -> None:
            counters["session_instances"] += 1
            self.session_id = session_id
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(self.db_path, timeout=15, check_same_thread=False)
            self.connection.execute(
                """CREATE TABLE IF NOT EXISTS fake_agent_session_item(
                    session_id TEXT NOT NULL,
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_json TEXT NOT NULL
                )"""
            )
            self.connection.commit()
            self.closed = False

        async def get_items(self, limit: int | None = None):
            sql = (
                "SELECT item_json FROM fake_agent_session_item WHERE session_id=? "
                "ORDER BY sequence ASC"
            )
            rows = self.connection.execute(sql, (self.session_id,)).fetchall()
            items = [json.loads(row[0]) for row in rows]
            return items[-limit:] if limit is not None else items

        async def add_items(self, items):
            self.connection.executemany(
                "INSERT INTO fake_agent_session_item(session_id,item_json) VALUES(?,?)",
                [
                    (self.session_id, json.dumps(item, ensure_ascii=False, sort_keys=True))
                    for item in items
                ],
            )
            self.connection.commit()

        async def pop_item(self):
            row = self.connection.execute(
                "SELECT sequence,item_json FROM fake_agent_session_item WHERE session_id=? ORDER BY sequence DESC LIMIT 1",
                (self.session_id,),
            ).fetchone()
            if row is None:
                return None
            self.connection.execute("DELETE FROM fake_agent_session_item WHERE sequence=?", (row[0],))
            self.connection.commit()
            return json.loads(row[1])

        async def clear_session(self):
            self.connection.execute(
                "DELETE FROM fake_agent_session_item WHERE session_id=?", (self.session_id,)
            )
            self.connection.commit()

        def close(self) -> None:
            if not self.closed:
                self.closed = True
                counters["session_closes"] += 1
                self.connection.close()

    class FakeAgent:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeRunConfig:
        def __init__(self, **kwargs):
            self.values = kwargs

    class FakeRunHooks:
        pass

    class FakeStreamingResult:
        def __init__(self, *, agent, request: str, session, hooks, turn_number: int) -> None:
            self.agent = agent
            self.request = request
            self.session = session
            self.hooks = hooks
            self.turn_number = turn_number
            self.last_response_id = f"resp-step043-turn-{turn_number}"
            self.context_wrapper = SimpleNamespace(
                usage=_usage(14, 5) if turn_number == 1 else _usage(20, 7)
            )
            self._output: CodingAgentResult | None = None

        async def stream_events(self):
            history = await self.session.get_items()
            captured["history_before"].append(history)
            captured["session_ids"].append(self.session.session_id)
            if self.turn_number == 1:
                summary = "Stored the project code for this Session."
            else:
                history_text = json.dumps(history, ensure_ascii=False)
                if RAW_SENTINEL not in history_text:
                    raise AssertionError("Turn 2 did not receive Turn 1 Session history")
                summary = "The project code is ORBIT-7."
            self._output = CodingAgentResult(
                status=AgentStatus.PASS,
                summary=summary,
                findings=[],
                unverified=[],
            )
            await self.hooks.on_agent_start(SimpleNamespace(), self.agent)
            await self.hooks.on_llm_start(
                SimpleNamespace(), self.agent, self.agent.instructions, [{"role": "user"}]
            )
            yield SimpleNamespace(type="agent_updated_stream_event", new_agent=self.agent)
            yield SimpleNamespace(
                type="raw_response_event",
                data=SimpleNamespace(type="response.output_text.delta", delta=summary),
            )
            await self.session.add_items(
                [
                    {"role": "user", "content": self.request},
                    {"role": "assistant", "content": summary},
                ]
            )
            response = SimpleNamespace(
                response_id=self.last_response_id,
                request_id=f"req-step043-{self.turn_number}",
                output=[1],
            )
            await self.hooks.on_llm_end(SimpleNamespace(), self.agent, response)
            await self.hooks.on_agent_end(SimpleNamespace(), self.agent, self._output)

        def final_output_as(self, output_type, raise_if_incorrect_type=False):
            assert output_type is CodingAgentResult
            assert raise_if_incorrect_type is True
            assert self._output is not None
            return self._output

    class FakeRunner:
        @classmethod
        async def run(cls, *args, **kwargs):
            counters["run"] += 1
            raise AssertionError("STEP043 must use Runner.run_streamed")

        @classmethod
        def run_streamed(cls, agent, request, **kwargs):
            counters["run_streamed"] += 1
            session = kwargs.get("session")
            if session is None:
                raise AssertionError("STEP043 requires installed SDK SQLiteSession")
            return FakeStreamingResult(
                agent=agent,
                request=request,
                session=session,
                hooks=kwargs["hooks"],
                turn_number=counters["run_streamed"],
            )

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
    fake_agents.SQLiteSession = FakeSQLiteSession
    fake_agents.gen_trace_id = lambda: "trace-step043"
    fake_agents.set_default_openai_key = lambda value: None
    sys.modules["agents"] = fake_agents
    importlib.metadata.version = (
        lambda name: "0.19.0" if name == "openai-agents" else previous_version(name)
    )
    return counters, captured, previous_version, previous_agents


def _restore(previous_version, previous_agents) -> None:
    importlib.metadata.version = previous_version
    if previous_agents is None:
        sys.modules.pop("agents", None)
    else:
        sys.modules["agents"] = previous_agents


def _wait_terminal(client: TestClient, run_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        body = client.get(f"/v1/runs/{run_id}", headers=ADMIN_HEADERS).json()
        if body.get("status") in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return body
        time.sleep(0.02)
    raise RuntimeError("STEP043 Run did not reach terminal state")


def _run_turn(
    client: TestClient,
    *,
    session_id: str,
    request: str,
    idempotency_key: str,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    preflight_response = client.post(
        "/v1/run-submissions/preflight",
        headers=SUBMIT_HEADERS,
        json={
            "agent_definition_id": "session-continuity-agent",
            "input": request,
            "model": "deterministic-step043-model",
            "session_id": session_id,
            "idempotency_key": idempotency_key,
        },
    )
    preflight = preflight_response.json()
    confirmed_response = client.post(
        f"/v1/run-submissions/{preflight['submission_id']}/confirm",
        headers=SUBMIT_HEADERS,
        json={"confirmation": preflight["confirmation_challenge"]},
    )
    confirmed = confirmed_response.json()
    terminal = _wait_terminal(client, confirmed["run_id"])
    return preflight, confirmed, terminal


def _counts(product_db: Path, evaluation_db: Path) -> dict[str, int]:
    product = sqlite3.connect(product_db)
    evaluation = sqlite3.connect(evaluation_db)
    try:
        return {
            "tasks": int(product.execute("SELECT COUNT(*) FROM task").fetchone()[0]),
            "runs": int(product.execute("SELECT COUNT(*) FROM run").fetchone()[0]),
            "submissions": int(
                product.execute("SELECT COUNT(*) FROM run_submission_preflight").fetchone()[0]
            ),
            "invocations": int(
                product.execute("SELECT COUNT(*) FROM agent_invocation").fetchone()[0]
            ),
            "events": int(product.execute("SELECT COUNT(*) FROM run_event").fetchone()[0]),
            "artifacts": int(product.execute("SELECT COUNT(*) FROM artifact").fetchone()[0]),
            "evaluations": int(
                evaluation.execute("SELECT COUNT(*) FROM evaluation_result").fetchone()[0]
            ),
        }
    finally:
        product.close()
        evaluation.close()


def run_acceptance(output: Path) -> int:
    references_before = {
        item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()
    }
    counters, captured, previous_version, previous_agents = _install_fake_agents()
    previous_key = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = HIDDEN_API_KEY
    try:
        with AcceptanceWorkspace(step_id="STEP043", output=output) as workspace:
            product_db = workspace.database_dir / "product.sqlite3"
            evaluation_db = workspace.database_dir / "evaluation.sqlite3"
            session_root = workspace.scratch_dir / "sessions"
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
                session_root=session_root,
                session_history_key=SESSION_HISTORY_KEY,
            )
            with TestClient(app) as client:
                unauthenticated = client.get("/v1/sessions")
                create_response = client.post(
                    "/v1/sessions",
                    headers=SUBMIT_HEADERS,
                    json={"agent_definition_id": "session-continuity-agent"},
                )
                created = create_response.json()
                session_id = created["session_id"]
                listed = client.get("/v1/sessions", headers=ADMIN_HEADERS).json()

                preflight1, confirmed1, terminal1 = _run_turn(
                    client,
                    session_id=session_id,
                    request=TURN1_REQUEST,
                    idempotency_key="step043-session-turn-one-0001",
                )
                session_after_turn1 = client.get(
                    f"/v1/sessions/{session_id}", headers=ADMIN_HEADERS
                ).json()
                events1 = client.get(
                    f"/v1/runs/{confirmed1['run_id']}/events", headers=ADMIN_HEADERS
                ).json()["events"]
                invocations1 = client.get(
                    f"/v1/runs/{confirmed1['run_id']}/invocations", headers=ADMIN_HEADERS
                ).json()["invocations"]

                preflight2, confirmed2, terminal2 = _run_turn(
                    client,
                    session_id=session_id,
                    request=TURN2_REQUEST,
                    idempotency_key="step043-session-turn-two-0002",
                )
                session_after_turn2 = client.get(
                    f"/v1/sessions/{session_id}", headers=ADMIN_HEADERS
                ).json()
                events2 = client.get(
                    f"/v1/runs/{confirmed2['run_id']}/events", headers=ADMIN_HEADERS
                ).json()["events"]
                invocations2 = client.get(
                    f"/v1/runs/{confirmed2['run_id']}/invocations", headers=ADMIN_HEADERS
                ).json()["invocations"]
                artifact2 = client.get(
                    f"/v1/runs/{confirmed2['run_id']}/artifact", headers=ADMIN_HEADERS
                ).json()
                evaluation_response = client.post(
                    f"/v1/runs/{confirmed2['run_id']}/evaluations",
                    headers=ADMIN_HEADERS,
                    json={"case_id": "sqlite-session-v1"},
                )
                evaluation = evaluation_response.json()
                submissions = [
                    client.get(
                        f"/v1/run-submissions/{preflight1['submission_id']}",
                        headers=ADMIN_HEADERS,
                    ).json(),
                    client.get(
                        f"/v1/run-submissions/{preflight2['submission_id']}",
                        headers=ADMIN_HEADERS,
                    ).json(),
                ]

                definition = AgentDefinitionCatalog(ROOT).resolve("session-continuity-agent")
                binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
                runtime = app.state.session_runtime
                runtime.acquire_turn(
                    session_id=session_id,
                    run_id="run_step043_exclusive_a",
                    definition=definition,
                    runtime_binding_sha256=binding.runtime_binding_sha256,
                )
                busy_rejected = False
                try:
                    runtime.acquire_turn(
                        session_id=session_id,
                        run_id="run_step043_exclusive_b",
                        definition=definition,
                        runtime_binding_sha256=binding.runtime_binding_sha256,
                    )
                except SessionBusyError:
                    busy_rejected = True
                runtime.release_turn(
                    session_id=session_id,
                    run_id="run_step043_exclusive_a",
                    succeeded=False,
                    item_count=4,
                )

                clear_response = client.post(
                    f"/v1/sessions/{session_id}/clear", headers=SUBMIT_HEADERS
                )
                cleared = clear_response.json()
                cleared_preflight = client.post(
                    "/v1/run-submissions/preflight",
                    headers=SUBMIT_HEADERS,
                    json={
                        "agent_definition_id": "session-continuity-agent",
                        "input": "This cleared Session must not execute.",
                        "model": "deterministic-step043-model",
                        "session_id": session_id,
                        "idempotency_key": "step043-cleared-session-block-0003",
                    },
                )

            references_after = {
                item.reference_id: item.to_dict()
                for item in ReferenceCatalogService(ROOT).verify_all()
            }
            history_db = session_root / "history.sqlite3"
            history_connection = sqlite3.connect(history_db)
            try:
                history_count_after_clear = int(
                    history_connection.execute(
                        "SELECT COUNT(*) FROM fake_agent_session_item WHERE session_id=?",
                        (session_id,),
                    ).fetchone()[0]
                )
            finally:
                history_connection.close()
            product_text = product_db.read_bytes().decode("utf-8", errors="ignore")
            evaluation_text = evaluation_db.read_bytes().decode("utf-8", errors="ignore")
            event_text = json.dumps(events1 + events2, ensure_ascii=False)
            final_counts = _counts(product_db, evaluation_db)
            history_before = captured["history_before"]
            started1 = [e for e in events1 if e["event_type"] == "session.turn.started"]
            completed1 = [e for e in events1 if e["event_type"] == "session.turn.completed"]
            started2 = [e for e in events2 if e["event_type"] == "session.turn.started"]
            completed2 = [e for e in events2 if e["event_type"] == "session.turn.completed"]
            checks = {
                "session_api_auth_required": unauthenticated.status_code == 401,
                "session_created_for_exact_agent_and_binding": create_response.status_code == 201
                and created.get("state") == "ACTIVE"
                and created.get("agent_definition_id") == "session-continuity-agent"
                and created.get("runtime_binding_sha256") == binding.runtime_binding_sha256,
                "session_catalog_lists_created_session": listed.get("total") == 1
                and listed.get("sessions", [])[0].get("session_id") == session_id,
                "two_governed_preflights_bound_same_session": preflight1.get("session_id") == session_id
                and preflight2.get("session_id") == session_id
                and preflight1.get("execution_mode") == "IMMEDIATE_AFTER_CONFIRMATION"
                and preflight2.get("execution_mode") == "IMMEDIATE_AFTER_CONFIRMATION",
                "native_streaming_runner_used_twice": counters["run_streamed"] == 2
                and counters["run"] == 0,
                "same_sdk_session_identity_used_twice": captured["session_ids"] == [session_id, session_id],
                "turn_one_started_without_history": len(history_before) == 2
                and history_before[0] == [],
                "turn_two_received_turn_one_history": len(history_before[1]) == 2
                and RAW_SENTINEL in json.dumps(history_before[1], ensure_ascii=False),
                "both_product_runs_succeeded": terminal1.get("status") == "SUCCEEDED"
                and terminal2.get("status") == "SUCCEEDED",
                "turn_one_session_metadata_exact": session_after_turn1.get("turn_count") == 1
                and session_after_turn1.get("item_count") == 2
                and session_after_turn1.get("active_run_id") is None,
                "turn_two_session_metadata_exact": session_after_turn2.get("turn_count") == 2
                and session_after_turn2.get("item_count") == 4
                and session_after_turn2.get("active_run_id") is None,
                "canonical_turn_events_exact": len(started1) == len(completed1) == 1
                and len(started2) == len(completed2) == 1
                and started1[0]["payload"].get("turn_ordinal") == 1
                and started2[0]["payload"].get("turn_ordinal") == 2
                and completed1[0]["payload"].get("item_count") == 2
                and completed2[0]["payload"].get("item_count") == 4,
                "session_history_not_copied_to_product_events": RAW_SENTINEL not in event_text
                and TURN1_REQUEST not in event_text
                and TURN2_REQUEST not in event_text,
                "session_history_not_copied_to_product_or_evaluation_db": RAW_SENTINEL not in product_text
                and TURN1_REQUEST not in product_text
                and TURN2_REQUEST not in product_text
                and RAW_SENTINEL not in evaluation_text
                and TURN1_REQUEST not in evaluation_text
                and TURN2_REQUEST not in evaluation_text,
                "sdk_session_history_persisted_before_clear": len(history_before[1]) == 2,
                "two_root_invocations_succeeded_without_workspace": len(invocations1) == 1
                and len(invocations2) == 1
                and all(
                    item["invocation_kind"] == "ROOT"
                    and item["state"] == "SUCCEEDED"
                    and item["workspace_access"] == "none"
                    and item["workspace_ref"] is None
                    for item in invocations1 + invocations2
                ),
                "turn_two_artifact_proves_continuity": artifact2.get("content", {}).get("status") == "PASS"
                and RAW_SENTINEL in artifact2.get("content", {}).get("summary", ""),
                "recorded_evaluation_passed": evaluation_response.status_code == 201
                and evaluation.get("state") == "PASSED"
                and evaluation.get("case_id") == "sqlite-session-v1",
                "successful_payloads_deleted": all(
                    item.get("payload_retention_state") == "DELETED" for item in submissions
                )
                and list(payload_root.glob("*.payload")) == [],
                "one_active_turn_enforced": busy_rejected is True,
                "failed_exclusivity_probe_did_not_increment_turn": runtime.get(session_id).turn_count == 2,
                "explicit_clear_marks_session_and_removes_history": clear_response.status_code == 200
                and cleared.get("state") == "CLEARED"
                and cleared.get("turn_count") == 2
                and cleared.get("item_count") == 0
                and cleared.get("cleared_at")
                and history_count_after_clear == 0,
                "cleared_session_cannot_preflight": cleared_preflight.status_code == 422
                and cleared_preflight.json().get("code")
                == "RUN_SUBMISSION_INVALID",
                "session_and_workspace_lifecycles_separate": not any(
                    path.is_dir() and path.name.startswith("invocation_")
                    for path in workspace.scratch_dir.rglob("*")
                ),
                "product_counts_exact": final_counts
                == {
                    "tasks": 2,
                    "runs": 2,
                    "submissions": 2,
                    "invocations": 2,
                    "events": len(events1) + len(events2),
                    "artifacts": 2,
                    "evaluations": 1,
                },
                "api_keys_not_persisted": HIDDEN_API_KEY not in product_text
                and HIDDEN_API_KEY not in evaluation_text,
                "session_handles_closed": counters["session_closes"] == counters["session_instances"],
                "references_unchanged": references_before == references_after,
                "cleanup_completed": True,
            }
            report = {
                "schema_version": "okcanvas-step043-acceptance-v1",
                "state": "PASSED" if all(checks.values()) else "FAILED",
                "checks": checks,
                "session": {
                    "session_id": session_id,
                    "runtime_binding_sha256": binding.runtime_binding_sha256,
                    "after_turn_1": session_after_turn1,
                    "after_turn_2": session_after_turn2,
                    "cleared": cleared,
                    "history_items_after_clear": history_count_after_clear,
                },
                "runs": {
                    "turn_1": {
                        "run_id": confirmed1["run_id"],
                        "submission_id": preflight1["submission_id"],
                        "event_count": len(events1),
                    },
                    "turn_2": {
                        "run_id": confirmed2["run_id"],
                        "submission_id": preflight2["submission_id"],
                        "event_count": len(events2),
                    },
                },
                "gateway_counts": counters,
                "final_counts": final_counts,
                "artifact_id": artifact2.get("artifact_id"),
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
        _restore(previous_version, previous_agents)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP043_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
