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

ADMIN_KEY = "step049-local-admin-key"
SUBMITTER_KEY = "step049-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SESSION_HISTORY_KEY = base64.urlsafe_b64encode(
    bytes((index + 67) % 256 for index in range(32))
).decode("ascii")
ADMIN_HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
SUBMIT_HEADERS = {**ADMIN_HEADERS, "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY}
AGENT_ID = "session-agent-tool-manager-agent"
TURN1_REQUEST = "Remember Session marker AURORA-49 and ask the declared specialist to analyze it."
TURN2_REQUEST = "Ask the specialist again and report the marker committed by the prior Turn."
MARKER = "AURORA-49"
RAW_ARGUMENT_SENTINEL = "STEP049-RAW-CHILD-ARGUMENT-MUST-NOT-ENTER-PRODUCT"
RAW_RESULT_SENTINEL = "STEP049-RAW-CHILD-RESULT-MUST-NOT-ENTER-PRODUCT"
HIDDEN_API_KEY = "step049-hidden-api-key"


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
        "session_instances": 0,
        "session_closes": 0,
    }
    captured: dict[str, object] = {
        "history_before": [],
        "root_session_ids": [],
        "child_sessions": [],
        "child_run_configs": [],
        "bounded_child_results": [],
    }
    previous_modules = {"agents": sys.modules.get("agents"), "openai": sys.modules.get("openai")}
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
            turn_number = counters["agent_tool_invoked"]
            captured["child_sessions"].append(self._kwargs["session"])
            captured["child_run_configs"].append(self._kwargs["run_config"].values)
            before = _usage(10 + turn_number, 3)
            after = _usage(24 + turn_number * 2, 7 + turn_number)
            child_output = CodingAgentResult(
                status=AgentStatus.PASS,
                summary=f"Nested specialist handled Turn {turn_number} with marker {MARKER}.",
                findings=[],
                unverified=[],
            )
            hooks = self._kwargs["hooks"]
            await hooks.on_agent_start(SimpleNamespace(usage=before), self.child)
            await hooks.on_llm_start(
                SimpleNamespace(usage=before), self.child, self.child.instructions, [{"role": "user"}]
            )
            on_stream = self._kwargs["on_stream"]
            await on_stream(
                {
                    "event": SimpleNamespace(type="agent_updated_stream_event", new_agent=self.child),
                    "agent": self.child,
                    "tool_call": SimpleNamespace(call_id=f"nested-call-{turn_number}"),
                }
            )
            await on_stream(
                {
                    "event": SimpleNamespace(
                        type="raw_response_event",
                        data=SimpleNamespace(
                            type="response.output_text.delta", delta=f"Nested Turn {turn_number}"
                        ),
                    ),
                    "agent": self.child,
                    "tool_call": SimpleNamespace(call_id=f"nested-call-{turn_number}"),
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
                    "tool_call": SimpleNamespace(call_id=f"nested-call-{turn_number}"),
                }
            )
            await hooks.on_llm_end(
                SimpleNamespace(usage=after),
                self.child,
                SimpleNamespace(
                    response_id=f"resp-step049-child-{turn_number}",
                    request_id=f"req-step049-child-{turn_number}",
                    output=[1],
                ),
            )
            await hooks.on_agent_end(SimpleNamespace(usage=after), self.child, child_output)

            class NestedResult:
                context_wrapper = SimpleNamespace(usage=after)
                final_output = child_output
                new_items = []

                def final_output_as(self, output_type, raise_if_incorrect_type=False):
                    assert output_type is CodingAgentResult
                    assert raise_if_incorrect_type is True
                    return child_output

            result = await self._kwargs["custom_output_extractor"](NestedResult())
            captured["bounded_child_results"].append(result)
            return result

    class FakeAgent:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

        def as_tool(self, **kwargs):
            counters["as_tool_constructed"] += 1
            return FakeAgentTool(self, **kwargs)

    class FakeStreamingResult:
        def __init__(self, *, parent, request: str, session, hooks, turn_number: int) -> None:
            self.parent = parent
            self.request = request
            self.session = session
            self.hooks = hooks
            self.turn_number = turn_number
            self.last_response_id = f"resp-step049-parent-{turn_number}"
            self.parent_before = _usage(10 + turn_number, 3)
            self.after_child = _usage(24 + turn_number * 2, 7 + turn_number)
            self.total_usage = _usage(36 + turn_number * 3, 12 + turn_number)
            self.context_wrapper = SimpleNamespace(usage=self.total_usage)
            self._output: CodingAgentResult | None = None

        async def stream_events(self):
            history = await self.session.get_items()
            captured["history_before"].append(history)
            captured["root_session_ids"].append(self.session.session_id)
            if self.turn_number == 2 and MARKER not in json.dumps(history, ensure_ascii=False):
                raise AssertionError("Turn 2 did not receive the committed Turn 1 Session history")
            parent = self.parent
            tool = parent.tools[0]
            hooks = self.hooks
            summary = (
                f"Root retained control and committed marker {MARKER} on Turn {self.turn_number}."
            )
            self._output = CodingAgentResult(
                status=AgentStatus.PASS,
                summary=summary,
                findings=[],
                unverified=[],
            )
            await hooks.on_agent_start(SimpleNamespace(usage=_usage(0, 0)), parent)
            await hooks.on_llm_start(
                SimpleNamespace(usage=_usage(0, 0)), parent, parent.instructions, [{"role": "user"}]
            )
            await hooks.on_llm_end(
                SimpleNamespace(usage=self.parent_before),
                parent,
                SimpleNamespace(
                    response_id=f"resp-step049-parent-before-{self.turn_number}",
                    request_id=f"req-step049-parent-before-{self.turn_number}",
                    output=[1],
                ),
            )
            tool_context = SimpleNamespace(
                tool_name=tool.name,
                tool_call_id=f"agent-tool-call-{self.turn_number}",
                tool_arguments=json.dumps(
                    {"input": f"{RAW_ARGUMENT_SENTINEL}-{self.turn_number}"},
                    separators=(",", ":"),
                ),
                tool_call=SimpleNamespace(call_id=f"agent-tool-call-{self.turn_number}"),
                usage=self.parent_before,
                run_config=SimpleNamespace(parent=True),
                context=None,
            )
            await hooks.on_tool_start(tool_context, parent, tool)
            bounded_result = await tool.on_invoke_tool(tool_context, tool_context.tool_arguments)
            tool_context.usage = self.after_child
            await hooks.on_tool_end(tool_context, parent, tool, bounded_result)
            await hooks.on_llm_start(
                SimpleNamespace(usage=self.after_child),
                parent,
                parent.instructions,
                [{"role": "tool"}],
            )
            await hooks.on_llm_end(
                SimpleNamespace(usage=self.total_usage),
                parent,
                SimpleNamespace(
                    response_id=self.last_response_id,
                    request_id=f"req-step049-parent-final-{self.turn_number}",
                    output=[1],
                ),
            )
            await hooks.on_agent_end(SimpleNamespace(usage=self.total_usage), parent, self._output)
            await self.session.add_items(
                [
                    {"role": "user", "content": self.request},
                    {"type": "function_call", "name": tool.name, "arguments": "bounded"},
                    {"type": "function_call_output", "name": tool.name, "output": "bounded"},
                    {"role": "assistant", "content": summary},
                ]
            )
            yield SimpleNamespace(
                type="raw_response_event",
                data=SimpleNamespace(type="response.output_text.delta", delta=summary),
            )

        def final_output_as(self, output_type, raise_if_incorrect_type=False):
            assert output_type is CodingAgentResult
            assert raise_if_incorrect_type is True
            assert self._output is not None
            return self._output

    class FakeRunner:
        @classmethod
        async def run(cls, *args, **kwargs):
            counters["run"] += 1
            raise AssertionError("STEP049 must use Runner.run_streamed")

        @classmethod
        def run_streamed(cls, agent, request, **kwargs):
            counters["outer_run_streamed"] += 1
            session = kwargs.get("session")
            if session is None:
                raise AssertionError("STEP049 Root requires installed SDK SQLiteSession")
            return FakeStreamingResult(
                parent=agent,
                request=request,
                session=session,
                hooks=kwargs["hooks"],
                turn_number=counters["outer_run_streamed"],
            )

    class FakeModelSettings:
        def __init__(self, **kwargs):
            self.values = kwargs

    fake_agents.Agent = FakeAgent
    fake_agents.ModelRetrySettings = FakeModelRetrySettings
    fake_agents.retry_policies = FakeRetryPolicies()
    fake_agents.OpenAIProvider = FakeOpenAIProvider
    fake_agents.RunConfig = FakeRunConfig
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_agents.ModelSettings = FakeModelSettings
    fake_agents.SQLiteSession = FakeSQLiteSession
    fake_agents.gen_trace_id = lambda: "trace-step049"
    fake_agents.set_default_openai_key = lambda value: None
    fake_openai.AsyncOpenAI = FakeAsyncOpenAI
    sys.modules["agents"] = fake_agents
    sys.modules["openai"] = fake_openai
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
    raise RuntimeError("STEP049 Run did not reach terminal state")


def _run_turn(client: TestClient, *, session_id: str, request: str, idempotency_key: str):
    preflight_response = client.post(
        "/v1/run-submissions/preflight",
        headers=SUBMIT_HEADERS,
        json={
            "agent_definition_id": AGENT_ID,
            "input": request,
            "model": "deterministic-step049-model",
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


def _history_count(history_db: Path, session_id: str) -> int:
    connection = sqlite3.connect(history_db)
    try:
        return int(
            connection.execute(
                "SELECT COUNT(*) FROM fake_agent_session_item WHERE session_id=?",
                (session_id,),
            ).fetchone()[0]
        )
    finally:
        connection.close()


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
        with AcceptanceWorkspace(step_id="STEP049", output=output) as workspace:
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
                if create_response.status_code != 201:
                    raise AssertionError(create_response.text)
                created = create_response.json()
                session_id = created["session_id"]

                preflight1, confirmed1, terminal1 = _run_turn(
                    client,
                    session_id=session_id,
                    request=TURN1_REQUEST,
                    idempotency_key="step049-session-agent-tool-turn-one-0001",
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
                    idempotency_key="step049-session-agent-tool-turn-two-0002",
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
                    json={"case_id": "sqlite-session-native-agent-tool-v1"},
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
                    run_id="run_step049_exclusive_a",
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
                        run_id="run_step049_exclusive_b",
                        definition=definition,
                        runtime_binding_sha256=binding.runtime_binding_sha256,
                    )
                except SessionBusyError:
                    busy_rejected = True
                runtime.release_turn(
                    session_id=session_id,
                    run_id="run_step049_exclusive_a",
                    succeeded=False,
                    item_count=8,
                )
                final_session = client.get(
                    f"/v1/sessions/{session_id}", headers=ADMIN_HEADERS
                ).json()
                history_item_count = _history_count(runtime.history_db, session_id)

            references_after = {
                item.reference_id: item.to_dict()
                for item in ReferenceCatalogService(ROOT).verify_all()
            }
            final_counts = _counts(product_db, evaluation_db)
            product_text = product_db.read_bytes().decode("utf-8", errors="ignore")
            all_events = [*events1, *events2]
            all_invocations = [*invocations1, *invocations2]
            root_invocations = [i for i in all_invocations if i["invocation_kind"] == "ROOT"]
            child_invocations = [
                i for i in all_invocations if i["invocation_kind"] == "AGENT_AS_TOOL"
            ]
            started = [e for e in all_events if e["event_type"] == "agent.tool.started"]
            completed = [e for e in all_events if e["event_type"] == "agent.tool.completed"]
            session_started = [e for e in all_events if e["event_type"] == "session.turn.started"]
            session_completed = [e for e in all_events if e["event_type"] == "session.turn.completed"]
            histories = captured["history_before"]
            bounded_results = captured["bounded_child_results"]
            child_configs = captured["child_run_configs"]
            session_ids = captured["root_session_ids"]
            checks = {
                "session_api_auth_required": unauthenticated.status_code == 401,
                "session_created_for_exact_agent_and_binding": created.get("agent_definition_id") == AGENT_ID
                and created.get("runtime_binding_sha256") == preflight1.get("runtime_binding_sha256")
                and binding.execution_path == "sqlite-session-native-agent-tool-execution-v1",
                "two_preflights_bound_same_session": preflight1.get("session_id") == session_id
                and preflight2.get("session_id") == session_id,
                "native_streaming_and_nested_streaming_used_twice": counters["run"] == 0
                and counters["outer_run_streamed"] == 2
                and counters["nested_run_streamed"] == 2,
                "native_agent_as_tool_constructed_and_invoked_twice": counters["as_tool_constructed"] == 2
                and counters["agent_tool_invoked"] == 2,
                "same_root_sdk_session_identity_used_twice": session_ids == [session_id, session_id],
                "child_nested_runs_are_session_disabled": captured["child_sessions"] == [None, None],
                "turn_one_started_without_history": histories[0] == [],
                "turn_two_received_complete_turn_one_history": len(histories[1]) == 4
                and MARKER in json.dumps(histories[1], ensure_ascii=False),
                "both_runs_succeeded": terminal1.get("status") == "SUCCEEDED"
                and terminal2.get("status") == "SUCCEEDED",
                "session_metadata_after_turn_one_exact": session_after_turn1.get("turn_count") == 1
                and session_after_turn1.get("item_count") == 4
                and session_after_turn1.get("active_run_id") is None,
                "session_metadata_after_turn_two_exact": session_after_turn2.get("turn_count") == 2
                and session_after_turn2.get("item_count") == 8
                and session_after_turn2.get("active_run_id") is None,
                "one_agent_tool_call_per_turn": len(started) == 2 and len(completed) == 2,
                "canonical_session_event_pairs_exact": len(session_started) == 2
                and len(session_completed) == 2,
                "two_root_and_two_agent_tool_invocations_succeeded": len(root_invocations) == 2
                and len(child_invocations) == 2
                and all(i["state"] == "SUCCEEDED" for i in all_invocations),
                "agent_tool_children_terminal_depth_one": all(
                    i["depth"] == 1 and i["parent_invocation_id"] == i["root_invocation_id"]
                    for i in child_invocations
                ),
                "parent_control_retained_after_each_child": all(
                    e["payload"].get("parent_control_retained") is True for e in completed
                ),
                "child_run_config_explicit_and_not_inherited": len(child_configs) == 2
                and all(
                    c.get("trace_metadata", {}).get("run_config_inherited") is False
                    and c.get("trace_metadata", {}).get("invocation_kind") == "AGENT_AS_TOOL"
                    for c in child_configs
                ),
                "bounded_structured_child_results_exact": len(bounded_results) == 2
                and all(str(r).startswith("{") and len(str(r).encode("utf-8")) <= 8192 for r in bounded_results),
                "turn_two_artifact_proves_session_agent_tool_continuity": artifact2.get("content", {}).get("status") == "PASS"
                and MARKER in artifact2.get("content", {}).get("summary", ""),
                "recorded_evaluation_passed": evaluation_response.status_code == 201
                and evaluation.get("state") == "PASSED",
                "confirmation_replay_no_duplicate": replay_response.status_code in {200, 202}
                and replay.get("replayed") is True
                and replay.get("scheduled") is False,
                "clear_rejected_while_turn_lease_held": clear_pending.status_code == 409,
                "competing_turn_rejected_while_lease_held": busy_rejected,
                "failed_exclusivity_probe_did_not_commit_turn": final_session.get("turn_count") == 2
                and final_session.get("item_count") == 8
                and final_session.get("active_run_id") is None,
                "sdk_history_contains_exactly_two_complete_agent_tool_turns": history_item_count == 8,
                "raw_session_and_child_content_not_in_product_events": TURN1_REQUEST not in product_text
                and TURN2_REQUEST not in product_text
                and RAW_ARGUMENT_SENTINEL not in product_text
                and RAW_RESULT_SENTINEL not in product_text,
                "raw_requests_and_api_key_not_in_product_or_evaluation_db": HIDDEN_API_KEY not in product_text
                and HIDDEN_API_KEY not in evaluation_db.read_bytes().decode("utf-8", errors="ignore"),
                "successful_payloads_deleted": list(payload_root.glob("*.payload")) == [],
                "session_handles_closed": counters["session_instances"] == 4
                and counters["session_closes"] == 4,
                "final_product_counts_exact": final_counts == {
                    "tasks": 2,
                    "runs": 2,
                    "submissions": 2,
                    "invocations": 4,
                    "events": len(all_events),
                    "artifacts": 2,
                    "evaluations": 1,
                },
                "references_unchanged": references_before == references_after,
                "cleanup_completed": True,
            }
            report = {
                "schema_version": "okcanvas-step049-acceptance-v1",
                "state": "PASSED" if all(checks.values()) else "FAILED",
                "checks": checks,
                "session": {
                    "session_id": session_id,
                    "runtime_binding_sha256": binding.runtime_binding_sha256,
                    "after_turn_1": session_after_turn1,
                    "after_turn_2": session_after_turn2,
                    "final": final_session,
                    "history_item_count": history_item_count,
                },
                "runs": {
                    "turn_1": {
                        "run_id": confirmed1["run_id"],
                        "event_count": len(events1),
                        "agent_tool_count": len([e for e in events1 if e["event_type"] == "agent.tool.started"]),
                    },
                    "turn_2": {
                        "run_id": confirmed2["run_id"],
                        "event_count": len(events2),
                        "agent_tool_count": len([e for e in events2 if e["event_type"] == "agent.tool.started"]),
                    },
                },
                "gateway_counts": counters,
                "final_counts": final_counts,
                "protected_payload_file_count": len(list(payload_root.glob("*.payload"))),
                "evaluation": evaluation,
                "replay": replay,
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
        "--output", type=Path, default=ROOT / "docs" / "evidence" / "STEP049_ACCEPTANCE.json"
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
