from __future__ import annotations

import argparse
import asyncio
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

ADMIN_KEY = "step047-local-admin-key"
SUBMITTER_KEY = "step047-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SESSION_HISTORY_KEY = base64.urlsafe_b64encode(
    bytes((index + 67) % 256 for index in range(32))
).decode("ascii")
ADMIN_HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
SUBMIT_HEADERS = {**ADMIN_HEADERS, "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY}
TURN1_REQUEST = "Remember the governed Session marker NEBULA-47, then transfer to the specialist."
TURN2_REQUEST = "Transfer again and report the Session marker from the previous Turn."
RAW_SENTINEL = "NEBULA-47"
HIDDEN_API_KEY = "step047-hidden-api-key"
AGENT_ID = "session-handoff-triage-agent"


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
        "run_streamed": 0,
        "handoff_constructed": 0,
        "session_instances": 0,
        "session_closes": 0,
    }
    captured: dict[str, object] = {
        "history_before": [],
        "session_ids": [],
        "handoff_session_ids": [],
    }
    module_names = ("agents", "agents.extensions", "agents.extensions.handoff_filters", "openai")
    previous_modules = {name: sys.modules.get(name) for name in module_names}
    previous_version = importlib.metadata.version
    fake_agents = types.ModuleType("agents")
    fake_openai = types.ModuleType("openai")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            self.kwargs = dict(kwargs)

    class FakeOpenAIProvider:
        def __init__(self, **kwargs):
            self.kwargs = dict(kwargs)
            self.closed = False

        def get_model(self, model_name):
            return SimpleNamespace(model_name=model_name)

        async def aclose(self):
            self.closed = True

    class FakeModelRetrySettings:
        def __init__(self, **kwargs):
            self.max_retries = kwargs.get("max_retries")
            self.policy = kwargs.get("policy")

    class FakeRetryPolicies:
        @staticmethod
        def never():
            return lambda _context: False
    extensions = types.ModuleType("agents.extensions")
    filters = types.ModuleType("agents.extensions.handoff_filters")

    def remove_all_tools(data):
        return data

    filters.remove_all_tools = remove_all_tools
    extensions.handoff_filters = filters

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
            rows = self.connection.execute(
                "SELECT item_json FROM fake_agent_session_item WHERE session_id=? ORDER BY sequence ASC",
                (self.session_id,),
            ).fetchall()
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

    class FakeStreamingResult:
        def __init__(self, *, root, request: str, session, hooks, turn_number: int) -> None:
            self.root = root
            self.request = request
            self.session = session
            self.hooks = hooks
            self.turn_number = turn_number
            self.last_response_id = f"resp-step047-child-{turn_number}"
            self.parent_usage = _usage(12 + turn_number, 4)
            self.total_usage = _usage(30 + turn_number * 2, 10 + turn_number)
            self.context_wrapper = SimpleNamespace(usage=self.total_usage)
            self._output: CodingAgentResult | None = None

        async def stream_events(self):
            history = await self.session.get_items()
            captured["history_before"].append(history)
            captured["session_ids"].append(self.session.session_id)
            root = self.root
            child = root.handoffs[0].agent
            hooks = self.hooks
            if self.turn_number == 1:
                summary = "SQLite Session native Handoff stored the governed marker."
            else:
                if RAW_SENTINEL not in json.dumps(history, ensure_ascii=False):
                    raise AssertionError("Turn 2 did not receive Turn 1 Session Handoff history")
                summary = "SQLite Session native Handoff recovered marker NEBULA-47."
            self._output = CodingAgentResult(
                status=AgentStatus.PASS,
                summary=summary,
                findings=[],
                unverified=[],
            )
            await hooks.on_agent_start(SimpleNamespace(usage=SimpleNamespace()), root)
            await hooks.on_llm_start(SimpleNamespace(), root, root.instructions, [{"role": "user"}])
            await hooks.on_llm_end(
                SimpleNamespace(usage=self.parent_usage),
                root,
                SimpleNamespace(
                    response_id=f"resp-step047-root-{self.turn_number}",
                    request_id=f"req-step047-root-{self.turn_number}",
                    output=[1],
                ),
            )
            captured["handoff_session_ids"].append(self.session.session_id)
            await hooks.on_handoff(SimpleNamespace(usage=self.parent_usage), root, child)
            yield SimpleNamespace(type="agent_updated_stream_event", new_agent=child)
            await hooks.on_agent_start(SimpleNamespace(usage=self.total_usage), child)
            await hooks.on_llm_start(SimpleNamespace(), child, child.instructions, [{"role": "user"}])
            yield SimpleNamespace(
                type="raw_response_event",
                data=SimpleNamespace(type="response.output_text.delta", delta=summary),
            )
            yield SimpleNamespace(
                type="run_item_stream_event",
                name="handoff_output_item",
                item=SimpleNamespace(type="handoff_output_item", agent=child, output=RAW_SENTINEL),
            )
            await self.session.add_items(
                [
                    {"role": "user", "content": self.request},
                    {"type": "handoff_call", "to": "handoff-specialist-agent"},
                    {"type": "handoff_output", "content": RAW_SENTINEL},
                    {"role": "assistant", "content": summary},
                ]
            )
            await hooks.on_llm_end(
                SimpleNamespace(usage=self.total_usage),
                child,
                SimpleNamespace(
                    response_id=self.last_response_id,
                    request_id=f"req-step047-child-{self.turn_number}",
                    output=[1],
                ),
            )
            await hooks.on_agent_end(SimpleNamespace(usage=self.total_usage), child, self._output)

        def final_output_as(self, output_type, raise_if_incorrect_type=False):
            assert output_type is CodingAgentResult
            assert raise_if_incorrect_type is True
            assert self._output is not None
            return self._output

    class FakeRunner:
        @classmethod
        async def run(cls, *args, **kwargs):
            counters["run"] += 1
            raise AssertionError("STEP047 must use Runner.run_streamed")

        @classmethod
        def run_streamed(cls, agent, request, **kwargs):
            counters["run_streamed"] += 1
            session = kwargs.get("session")
            if session is None:
                raise AssertionError("STEP047 requires installed SDK SQLiteSession")
            return FakeStreamingResult(
                root=agent,
                request=request,
                session=session,
                hooks=kwargs["hooks"],
                turn_number=counters["run_streamed"],
            )

    class FakeModelSettings:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    fake_agents.Agent = FakeAgent
    fake_agents.ModelSettings = FakeModelSettings
    fake_agents.ModelRetrySettings = FakeModelRetrySettings
    fake_agents.retry_policies = FakeRetryPolicies()
    fake_agents.OpenAIProvider = FakeOpenAIProvider
    fake_agents.RunConfig = FakeRunConfig
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_agents.SQLiteSession = FakeSQLiteSession
    fake_agents.handoff = fake_handoff
    fake_agents.gen_trace_id = lambda: "trace-step047"
    fake_agents.set_default_openai_key = lambda value: None
    fake_openai.AsyncOpenAI = FakeAsyncOpenAI
    sys.modules["agents"] = fake_agents
    sys.modules["openai"] = fake_openai
    sys.modules["agents.extensions"] = extensions
    sys.modules["agents.extensions.handoff_filters"] = filters
    importlib.metadata.version = (
        lambda name: "0.19.0" if name == "openai-agents" else previous_version(name)
    )
    return counters, captured, previous_version, previous_modules


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
    raise RuntimeError("STEP047 Run did not reach terminal state")


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
            "agent_definition_id": AGENT_ID,
            "input": request,
            "model": "deterministic-step047-model",
            "session_id": session_id,
            "idempotency_key": idempotency_key,
        },
    )
    if preflight_response.status_code != 201:
        raise AssertionError(preflight_response.text)
    preflight = preflight_response.json()
    confirmed_response = client.post(
        f"/v1/run-submissions/{preflight['submission_id']}/confirm",
        headers=SUBMIT_HEADERS,
        json={"confirmation": preflight["confirmation_challenge"]},
    )
    if confirmed_response.status_code not in {200, 202}:
        raise AssertionError(confirmed_response.text)
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
    os.environ["OPENAI_API_KEY"] = HIDDEN_API_KEY
    try:
        with AcceptanceWorkspace(step_id="STEP047", output=output) as workspace:
            product_db = workspace.database_dir / "product.sqlite3"
            evaluation_db = workspace.database_dir / "evaluation.sqlite3"
            session_root = workspace.scratch_dir / "sessions"
            payload_root = workspace.scratch_dir / "protected-payloads"
            app = create_app(
                project_root=ROOT,
                product_db=product_db,
                artifact_root=workspace.artifact_dir,
                evaluation_db=evaluation_db,
                admin_key=ADMIN_KEY,
                run_submitter_key=SUBMITTER_KEY,
                protected_payload_root=payload_root,
                protected_payload_key=PAYLOAD_KEY,
                native_stream_broker=InMemoryNativeSDKStreamBroker(),
                session_root=session_root,
                session_history_key=SESSION_HISTORY_KEY,
            )
            with TestClient(app) as client:
                unauthenticated = client.get("/v1/sessions")
                create_response = client.post(
                    "/v1/sessions",
                    headers=SUBMIT_HEADERS,
                    json={"agent_definition_id": AGENT_ID},
                )
                created = create_response.json()
                session_id = created["session_id"]

                preflight1, confirmed1, terminal1 = _run_turn(
                    client,
                    session_id=session_id,
                    request=TURN1_REQUEST,
                    idempotency_key="step047-session-handoff-turn-one-0001",
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
                    idempotency_key="step047-session-handoff-turn-two-0002",
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
                    json={"case_id": "sqlite-session-native-handoff-v1"},
                )
                evaluation = evaluation_response.json()

                replay_response = client.post(
                    f"/v1/run-submissions/{preflight2['submission_id']}/confirm",
                    headers=SUBMIT_HEADERS,
                    json={"confirmation": preflight2["confirmation_challenge"]},
                )
                replay = replay_response.json()

                definition = AgentDefinitionCatalog(ROOT).resolve(AGENT_ID)
                binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
                runtime = app.state.session_runtime
                runtime.acquire_turn(
                    session_id=session_id,
                    run_id="run_step047_exclusive_a",
                    definition=definition,
                    runtime_binding_sha256=binding.runtime_binding_sha256,
                )
                clear_pending = client.post(
                    f"/v1/sessions/{session_id}/clear", headers=SUBMIT_HEADERS
                )
                busy_rejected = False
                try:
                    runtime.acquire_turn(
                        session_id=session_id,
                        run_id="run_step047_exclusive_b",
                        definition=definition,
                        runtime_binding_sha256=binding.runtime_binding_sha256,
                    )
                except SessionBusyError:
                    busy_rejected = True
                runtime.release_turn(
                    session_id=session_id,
                    run_id="run_step047_exclusive_a",
                    succeeded=False,
                    item_count=8,
                )
                session_final = client.get(
                    f"/v1/sessions/{session_id}", headers=ADMIN_HEADERS
                ).json()
                submissions = [
                    client.get(
                        f"/v1/run-submissions/{item['submission_id']}", headers=ADMIN_HEADERS
                    ).json()
                    for item in (preflight1, preflight2)
                ]

            references_after = {
                item.reference_id: item.to_dict()
                for item in ReferenceCatalogService(ROOT).verify_all()
            }
            product_text = product_db.read_bytes().decode("utf-8", errors="ignore")
            evaluation_text = evaluation_db.read_bytes().decode("utf-8", errors="ignore")
            event_text = json.dumps(events1 + events2, ensure_ascii=False)
            final_counts = _counts(product_db, evaluation_db)
            encrypted_session = runtime.sdk_session(session_id)
            try:
                history_items = asyncio.run(encrypted_session.get_items())
            finally:
                encrypted_session.close()

            handoff_events1 = [e for e in events1 if e["event_type"] == "agent.handoff"]
            handoff_events2 = [e for e in events2 if e["event_type"] == "agent.handoff"]
            started = [e for e in events1 + events2 if e["event_type"] == "session.turn.started"]
            completed = [e for e in events1 + events2 if e["event_type"] == "session.turn.completed"]
            root_invocations = [
                item for item in invocations1 + invocations2 if item["invocation_kind"] == "ROOT"
            ]
            child_invocations = [
                item for item in invocations1 + invocations2 if item["invocation_kind"] == "HANDOFF"
            ]
            history_before = captured["history_before"]
            checks = {
                "session_api_auth_required": unauthenticated.status_code == 401,
                "session_created_for_exact_agent_and_binding": create_response.status_code == 201
                and created.get("agent_definition_id") == AGENT_ID
                and created.get("runtime_binding_sha256") == binding.runtime_binding_sha256
                and binding.execution_path == "sqlite-session-native-handoff-execution-v1",
                "two_preflights_bound_same_session": preflight1.get("session_id") == session_id
                and preflight2.get("session_id") == session_id
                and preflight1.get("execution_mode") == "IMMEDIATE_AFTER_CONFIRMATION"
                and preflight2.get("execution_mode") == "IMMEDIATE_AFTER_CONFIRMATION",
                "native_streaming_runner_used_twice": counters["run_streamed"] == 2
                and counters["run"] == 0,
                "native_handoff_constructed_twice": counters["handoff_constructed"] == 2,
                "same_sdk_session_identity_used_across_root_and_handoff": captured["session_ids"]
                == [session_id, session_id]
                and captured["handoff_session_ids"] == [session_id, session_id],
                "turn_one_started_without_history": len(history_before) == 2
                and history_before[0] == [],
                "turn_two_received_complete_turn_one_history": len(history_before[1]) == 4
                and RAW_SENTINEL in json.dumps(history_before[1], ensure_ascii=False),
                "both_runs_succeeded": terminal1.get("status") == "SUCCEEDED"
                and terminal2.get("status") == "SUCCEEDED",
                "session_metadata_after_turn_one_exact": session_after_turn1.get("turn_count") == 1
                and session_after_turn1.get("item_count") == 4
                and session_after_turn1.get("active_run_id") is None,
                "session_metadata_after_turn_two_exact": session_after_turn2.get("turn_count") == 2
                and session_after_turn2.get("item_count") == 8
                and session_after_turn2.get("active_run_id") is None,
                "one_native_handoff_per_turn": len(handoff_events1) == 1
                and len(handoff_events2) == 1
                and all(
                    event["payload"].get("from_agent_id") == AGENT_ID
                    and event["payload"].get("to_agent_id") == "handoff-specialist-agent"
                    and event["payload"].get("sdk_session_history_active") is True
                    and event["payload"].get("session_id_present") is True
                    for event in handoff_events1 + handoff_events2
                ),
                "canonical_session_event_pairs_exact": len(started) == 2
                and len(completed) == 2
                and [event["payload"].get("turn_ordinal") for event in started] == [1, 2]
                and [event["payload"].get("item_count") for event in completed] == [4, 8],
                "two_root_and_two_handoff_invocations_succeeded": len(root_invocations) == 2
                and len(child_invocations) == 2
                and all(item["state"] == "SUCCEEDED" for item in root_invocations + child_invocations),
                "handoff_children_are_terminal_depth_one": all(
                    item["agent_definition_id"] == "handoff-specialist-agent"
                    and item["depth"] == 1
                    and item["ordinal"] == 1
                    and item["workspace_access"] == "none"
                    and item["workspace_ref"] is None
                    for item in child_invocations
                ),
                "turn_two_artifact_proves_session_handoff_continuity": artifact2.get("content", {}).get("status") == "PASS"
                and RAW_SENTINEL in artifact2.get("content", {}).get("summary", ""),
                "recorded_evaluation_passed": evaluation_response.status_code == 201
                and evaluation.get("state") == "PASSED"
                and evaluation.get("case_id") == "sqlite-session-native-handoff-v1",
                "confirmation_replay_no_duplicate": replay_response.status_code in {200, 202}
                and replay.get("run_id") == confirmed2.get("run_id")
                and replay.get("scheduled") is False
                and replay.get("replayed") is True,
                "clear_rejected_while_turn_lease_held": clear_pending.status_code == 409,
                "competing_turn_rejected_while_lease_held": busy_rejected is True,
                "failed_exclusivity_probe_did_not_commit_turn": session_final.get("turn_count") == 2
                and session_final.get("item_count") == 8
                and session_final.get("active_run_id") is None,
                "sdk_history_contains_exactly_two_complete_handoff_turns": len(history_items) == 8
                and sum(item.get("type") == "handoff_call" for item in history_items) == 2
                and sum(item.get("type") == "handoff_output" for item in history_items) == 2,
                "raw_session_history_not_copied_to_product_events": RAW_SENTINEL not in event_text
                and TURN1_REQUEST not in event_text
                and TURN2_REQUEST not in event_text,
                "raw_requests_and_api_key_not_in_product_or_evaluation_db": RAW_SENTINEL not in product_text
                and TURN1_REQUEST not in product_text
                and TURN2_REQUEST not in product_text
                and HIDDEN_API_KEY not in product_text
                and RAW_SENTINEL not in evaluation_text
                and HIDDEN_API_KEY not in evaluation_text,
                "successful_payloads_deleted": all(
                    item.get("payload_retention_state") == "DELETED" for item in submissions
                )
                and not list(payload_root.glob("*.payload"))
                and not list(payload_root.glob("payload_*.json")),
                "session_handles_closed": counters["session_instances"] == counters["session_closes"],
                "final_product_counts_exact": final_counts
                == {
                    "tasks": 2,
                    "runs": 2,
                    "submissions": 2,
                    "invocations": 4,
                    "events": 32,
                    "artifacts": 2,
                    "evaluations": 1,
                },
                "references_unchanged": references_before == references_after,
                "cleanup_completed": True,
            }
            report = {
                "schema_version": "okcanvas-step047-acceptance-v1",
                "state": "PASSED" if all(checks.values()) else "FAILED",
                "checks": checks,
                "session": {
                    "session_id": session_id,
                    "runtime_binding_sha256": binding.runtime_binding_sha256,
                    "after_turn_1": session_after_turn1,
                    "after_turn_2": session_after_turn2,
                    "final": session_final,
                    "history_item_count": len(history_items),
                },
                "runs": {
                    "turn_1": {
                        "run_id": confirmed1["run_id"],
                        "event_count": len(events1),
                        "handoff_count": len(handoff_events1),
                    },
                    "turn_2": {
                        "run_id": confirmed2["run_id"],
                        "event_count": len(events2),
                        "handoff_count": len(handoff_events2),
                    },
                },
                "gateway_counts": counters,
                "final_counts": final_counts,
                "protected_payload_file_count": len(list(payload_root.glob("*"))),
                "evaluation": evaluation,
                "replay": {"status_code": replay_response.status_code, **replay},
            }
            final = workspace.finalize(report)
            final["checks"]["cleanup_completed"] = (
                final["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
            )
            final["state"] = "PASSED" if all(final["checks"].values()) else "FAILED"
            output.write_text(json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(final, ensure_ascii=False, indent=2))
            return 0 if final["state"] == "PASSED" else 1
    finally:
        if previous_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = previous_key
        _restore(previous_version, previous_modules)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP047_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
