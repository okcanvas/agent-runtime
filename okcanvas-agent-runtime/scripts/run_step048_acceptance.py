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

ADMIN_KEY = "step048-local-admin-key"
SUBMITTER_KEY = "step048-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SESSION_HISTORY_KEY = base64.urlsafe_b64encode(
    bytes((index + 67) % 256 for index in range(32))
).decode("ascii")
ADMIN_HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
SUBMIT_HEADERS = {**ADMIN_HEADERS, "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY}
HIDDEN_API_KEY = "step048-hidden-api-key"
AGENT_ID = "session-guardrail-language-agent"
MARKER = "ORBIT-48"
REQUESTS = {
    "clean_1": f"Remember the governed Session marker {MARKER}.",
    "input_trip": "BLOCK_INPUT protected STEP048 input must be rolled back.",
    "output_trip": "Produce the deterministic output guardrail marker for STEP048.",
    "clean_2": "Recall the governed Session marker from the prior successful Turn.",
}


def _usage(input_tokens: int, output_tokens: int):
    return SimpleNamespace(
        requests=1 if input_tokens or output_tokens else 0,
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
        "model_calls": 0,
        "guardrail_runs": {"INPUT": 0, "OUTPUT": 0},
        "session_instances": 0,
        "session_closes": 0,
    }
    captured: dict[str, list[object]] = {"history_before": [], "session_ids": []}
    module_names = ("agents", "agents.decorators", "openai")
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
    fake_decorators = types.ModuleType("agents.decorators")

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

    class FakeGuardrailFunctionOutput:
        def __init__(self, *, output_info, tripwire_triggered):
            self.output_info = output_info
            self.tripwire_triggered = tripwire_triggered

    class FakeInputGuardrail:
        def __init__(self, fn, name, run_in_parallel):
            self.fn = fn
            self.name = name
            self.run_in_parallel = run_in_parallel

        def get_name(self):
            return self.name

        async def run(self, context, agent, value):
            counters["guardrail_runs"]["INPUT"] += 1
            return await self.fn(context, agent, value)

    class FakeOutputGuardrail:
        def __init__(self, fn, name):
            self.fn = fn
            self.name = name

        def get_name(self):
            return self.name

        async def run(self, context, agent, value):
            counters["guardrail_runs"]["OUTPUT"] += 1
            return await self.fn(context, agent, value)

    def input_guardrail(func=None, *, name=None, run_in_parallel=True):
        def decorate(fn):
            return FakeInputGuardrail(fn, name or fn.__name__, run_in_parallel)

        return decorate(func) if func is not None else decorate

    def output_guardrail(func=None, *, name=None):
        def decorate(fn):
            return FakeOutputGuardrail(fn, name or fn.__name__)

        return decorate(func) if func is not None else decorate

    def unused_tool_guardrail(func=None, *, name=None):
        def decorate(fn):
            return fn

        return decorate(func) if func is not None else decorate

    class FakeException(Exception):
        def __init__(self, *args):
            super().__init__(*args)
            self.run_data = None

    class InputGuardrailTripwireTriggered(FakeException):
        def __init__(self, result):
            super().__init__("input guardrail")
            self.guardrail_result = result

    class OutputGuardrailTripwireTriggered(FakeException):
        def __init__(self, result):
            super().__init__("output guardrail")
            self.guardrail_result = result

    class ToolInputGuardrailTripwireTriggered(FakeException):
        pass

    class ToolOutputGuardrailTripwireTriggered(FakeException):
        pass

    class FakeAgent:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeRunConfig:
        def __init__(self, **kwargs):
            self.values = kwargs

    class FakeRunHooks:
        pass

    def _attach_run_data(exc, usage):
        exc.run_data = SimpleNamespace(context_wrapper=SimpleNamespace(usage=usage))
        return exc

    class FakeStreamingResult:
        def __init__(self, *, agent, request: str, session, hooks) -> None:
            self.agent = agent
            self.request = request
            self.session = session
            self.hooks = hooks
            self.last_response_id = None
            self.context_wrapper = SimpleNamespace(usage=_usage(0, 0))
            self._output: CodingAgentResult | None = None

        async def stream_events(self):
            history = await self.session.get_items()
            captured["history_before"].append(history)
            captured["session_ids"].append(self.session.session_id)

            # The installed SDK test proves an input tripwire may persist the user item.
            # Persist it before the check so Product rollback is exercised, not assumed.
            if "BLOCK_INPUT" in self.request:
                await self.session.add_items([{"role": "user", "content": self.request}])

            for guardrail in getattr(self.agent, "input_guardrails", []):
                result = await guardrail.run(SimpleNamespace(), self.agent, self.request)
                if result.tripwire_triggered:
                    raise _attach_run_data(
                        InputGuardrailTripwireTriggered(
                            SimpleNamespace(guardrail=guardrail, output=result)
                        ),
                        _usage(0, 0),
                    )

            await self.hooks.on_agent_start(SimpleNamespace(), self.agent)
            await self.hooks.on_llm_start(
                SimpleNamespace(), self.agent, self.agent.instructions, [{"role": "user"}]
            )
            counters["model_calls"] += 1
            if "output guardrail" in self.request:
                summary = "BLOCK_OUTPUT"
            elif "Recall" in self.request:
                history_text = json.dumps(history, ensure_ascii=False)
                if MARKER not in history_text:
                    raise AssertionError("Successful Session history did not reach the later Guardrail Turn")
                if "BLOCK_INPUT" in history_text or "BLOCK_OUTPUT" in history_text:
                    raise AssertionError("Tripwire content leaked into later Session history")
                summary = f"Recovered governed Session marker {MARKER}."
            else:
                summary = f"Stored governed Session marker {MARKER}."
            usage = _usage(11 + counters["model_calls"], 3)
            self.context_wrapper = SimpleNamespace(usage=usage)
            self._output = CodingAgentResult(
                status=AgentStatus.PASS,
                summary=summary,
                findings=[],
                unverified=[],
            )
            response = SimpleNamespace(
                response_id=f"resp-step048-{counters['model_calls']}",
                request_id=f"req-step048-{counters['model_calls']}",
                output=[1],
            )
            self.last_response_id = response.response_id
            await self.hooks.on_llm_end(SimpleNamespace(usage=usage), self.agent, response)

            # Persist both turn items before the output check. Product rollback must remove
            # the entire failed turn even under this worst-case partial-persistence order.
            await self.session.add_items(
                [
                    {"role": "user", "content": self.request},
                    {"role": "assistant", "content": summary},
                ]
            )
            for guardrail in getattr(self.agent, "output_guardrails", []):
                result = await guardrail.run(SimpleNamespace(), self.agent, self._output)
                if result.tripwire_triggered:
                    raise _attach_run_data(
                        OutputGuardrailTripwireTriggered(
                            SimpleNamespace(guardrail=guardrail, output=result)
                        ),
                        usage,
                    )
            await self.hooks.on_agent_end(SimpleNamespace(usage=usage), self.agent, self._output)
            yield SimpleNamespace(type="agent_updated_stream_event", new_agent=self.agent)
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
        async def run(cls, agent, request, **kwargs):
            counters["run"] += 1
            result = FakeStreamingResult(
                agent=agent,
                request=request,
                session=kwargs["session"],
                hooks=kwargs["hooks"],
            )
            async for _ in result.stream_events():
                pass
            return result

        @classmethod
        def run_streamed(cls, agent, request, **kwargs):
            counters["run_streamed"] += 1
            return FakeStreamingResult(
                agent=agent,
                request=request,
                session=kwargs["session"],
                hooks=kwargs["hooks"],
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
    fake_agents.GuardrailFunctionOutput = FakeGuardrailFunctionOutput
    fake_agents.InputGuardrailTripwireTriggered = InputGuardrailTripwireTriggered
    fake_agents.OutputGuardrailTripwireTriggered = OutputGuardrailTripwireTriggered
    fake_agents.ToolInputGuardrailTripwireTriggered = ToolInputGuardrailTripwireTriggered
    fake_agents.ToolOutputGuardrailTripwireTriggered = ToolOutputGuardrailTripwireTriggered
    fake_agents.gen_trace_id = lambda: "trace_step048"
    fake_agents.set_default_openai_key = lambda key: None
    fake_decorators.input_guardrail = input_guardrail
    fake_decorators.output_guardrail = output_guardrail
    fake_decorators.tool_input_guardrail = unused_tool_guardrail
    fake_decorators.tool_output_guardrail = unused_tool_guardrail
    fake_openai.AsyncOpenAI = FakeAsyncOpenAI
    sys.modules["agents"] = fake_agents
    sys.modules["openai"] = fake_openai
    sys.modules["agents.decorators"] = fake_decorators
    importlib.metadata.version = (
        lambda name: "0.19.0" if name == "openai-agents" else previous_version(name)
    )
    return counters, captured, previous_version, previous_modules


def _restore(previous_version, previous_modules):
    importlib.metadata.version = previous_version
    for name, module in previous_modules.items():
        if module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module


def _wait_terminal(client: TestClient, run_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        body = client.get(f"/v1/runs/{run_id}", headers=ADMIN_HEADERS).json()
        if body.get("status") in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return body
        time.sleep(0.02)
    raise RuntimeError("STEP048 Run did not terminate")


def _execute(client: TestClient, *, session_id: str, request: str, key: str):
    preflight_response = client.post(
        "/v1/run-submissions/preflight",
        headers=SUBMIT_HEADERS,
        json={
            "agent_definition_id": AGENT_ID,
            "session_id": session_id,
            "input": request,
            "model": "deterministic-step048-model",
            "idempotency_key": key,
        },
    )
    preflight = preflight_response.json()
    confirm_response = client.post(
        f"/v1/run-submissions/{preflight['submission_id']}/confirm",
        headers=SUBMIT_HEADERS,
        json={"confirmation": preflight["confirmation_challenge"]},
    )
    confirmed = confirm_response.json()
    if "run_id" not in confirmed:
        raise RuntimeError(f"STEP048 confirmation failed: preflight={preflight_response.status_code} {preflight!r}; confirm={confirm_response.status_code} {confirmed!r}")
    terminal = _wait_terminal(client, confirmed["run_id"])
    events = client.get(
        f"/v1/runs/{confirmed['run_id']}/events", headers=ADMIN_HEADERS
    ).json()["events"]
    invocations = client.get(
        f"/v1/runs/{confirmed['run_id']}/invocations", headers=ADMIN_HEADERS
    ).json()["invocations"]
    submission = client.get(
        f"/v1/run-submissions/{preflight['submission_id']}", headers=ADMIN_HEADERS
    ).json()
    return {
        "preflight_response": preflight_response,
        "preflight": preflight,
        "confirm_response": confirm_response,
        "confirmed": confirmed,
        "terminal": terminal,
        "events": events,
        "invocations": invocations,
        "submission": submission,
    }


def _counts(product_db: Path, evaluation_db: Path) -> dict[str, int]:
    product = sqlite3.connect(product_db)
    evaluation = sqlite3.connect(evaluation_db)
    try:
        return {
            "tasks": product.execute("select count(*) from task").fetchone()[0],
            "runs": product.execute("select count(*) from run").fetchone()[0],
            "submissions": product.execute(
                "select count(*) from run_submission_preflight"
            ).fetchone()[0],
            "invocations": product.execute("select count(*) from agent_invocation").fetchone()[0],
            "events": product.execute("select count(*) from run_event").fetchone()[0],
            "artifacts": product.execute("select count(*) from artifact").fetchone()[0],
            "evaluations": evaluation.execute(
                "select count(*) from evaluation_result"
            ).fetchone()[0],
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
        with AcceptanceWorkspace(step_id="STEP048", output=output) as workspace:
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

                cases = {}
                metadata = {}
                for index, name in enumerate(("clean_1", "input_trip", "output_trip", "clean_2"), 1):
                    cases[name] = _execute(
                        client,
                        session_id=session_id,
                        request=REQUESTS[name],
                        key=f"step048-{name}-{index:04d}",
                    )
                    metadata[name] = client.get(
                        f"/v1/sessions/{session_id}", headers=ADMIN_HEADERS
                    ).json()

                clean_2 = cases["clean_2"]
                artifact = client.get(
                    f"/v1/runs/{clean_2['confirmed']['run_id']}/artifact",
                    headers=ADMIN_HEADERS,
                ).json()
                evaluation_response = client.post(
                    f"/v1/runs/{clean_2['confirmed']['run_id']}/evaluations",
                    headers=ADMIN_HEADERS,
                    json={"case_id": "sqlite-session-native-guardrail-v1"},
                )
                evaluation = evaluation_response.json()

                replay_response = client.post(
                    f"/v1/run-submissions/{clean_2['preflight']['submission_id']}/confirm",
                    headers=SUBMIT_HEADERS,
                    json={"confirmation": clean_2["preflight"]["confirmation_challenge"]},
                )
                replay = replay_response.json()

                definition = AgentDefinitionCatalog(ROOT).resolve(AGENT_ID)
                binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
                runtime = app.state.session_runtime
                runtime.acquire_turn(
                    session_id=session_id,
                    run_id="run_step048_exclusive_a",
                    definition=definition,
                    runtime_binding_sha256=binding.runtime_binding_sha256,
                )
                clear_pending = client.post(
                    f"/v1/sessions/{session_id}/clear", headers=SUBMIT_HEADERS
                )
                competing_rejected = False
                try:
                    runtime.acquire_turn(
                        session_id=session_id,
                        run_id="run_step048_exclusive_b",
                        definition=definition,
                        runtime_binding_sha256=binding.runtime_binding_sha256,
                    )
                except SessionBusyError:
                    competing_rejected = True
                runtime.release_turn(
                    session_id=session_id,
                    run_id="run_step048_exclusive_a",
                    succeeded=False,
                    item_count=4,
                )
                final_session = client.get(
                    f"/v1/sessions/{session_id}", headers=ADMIN_HEADERS
                ).json()

            references_after = {
                item.reference_id: item.to_dict()
                for item in ReferenceCatalogService(ROOT).verify_all()
            }
            final_counts = _counts(product_db, evaluation_db)
            product_text = product_db.read_bytes().decode("utf-8", errors="ignore")
            evaluation_text = evaluation_db.read_bytes().decode("utf-8", errors="ignore")
            all_events = [event for case in cases.values() for event in case["events"]]
            event_text = json.dumps(all_events, ensure_ascii=False)
            encrypted_session = runtime.sdk_session(session_id)
            try:
                history_items = asyncio.run(encrypted_session.get_items())
            finally:
                encrypted_session.close()

            tripwire_events = {
                name: [e for e in case["events"] if e["event_type"] == "guardrail.tripped"]
                for name, case in cases.items()
            }
            started_events = [e for e in all_events if e["event_type"] == "session.turn.started"]
            completed_events = [e for e in all_events if e["event_type"] == "session.turn.completed"]
            checks = {
                "session_api_auth_required": unauthenticated.status_code == 401,
                "session_created_for_exact_agent_and_binding": create_response.status_code == 201
                and created.get("agent_definition_id") == AGENT_ID
                and created.get("runtime_binding_sha256") == binding.runtime_binding_sha256
                and binding.execution_path == "sqlite-session-native-guardrail-execution-v1",
                "four_preflights_bound_same_session": all(
                    case["preflight"].get("session_id") == session_id
                    and case["preflight"].get("execution_mode") == "IMMEDIATE_AFTER_CONFIRMATION"
                    for case in cases.values()
                ),
                "native_streaming_runner_used_four_times": counters["run_streamed"] == 4
                and counters["run"] == 0,
                "same_sdk_session_identity_used_four_times": captured["session_ids"]
                == [session_id] * 4,
                "first_success_committed_exactly_two_items": metadata["clean_1"].get("turn_count") == 1
                and metadata["clean_1"].get("item_count") == 2
                and metadata["clean_1"].get("active_run_id") is None,
                "input_tripwire_failed_before_model": cases["input_trip"]["terminal"].get("status") == "FAILED"
                and any(
                    e["event_type"] == "run.failed"
                    and e["payload"].get("code") == "INPUT_GUARDRAIL_TRIPPED"
                    for e in cases["input_trip"]["events"]
                )
                and counters["model_calls"] == 3,
                "input_tripwire_partial_history_rolled_back": metadata["input_trip"].get("turn_count") == 1
                and metadata["input_trip"].get("item_count") == 2
                and metadata["input_trip"].get("active_run_id") is None,
                "output_tripwire_failed_after_model": cases["output_trip"]["terminal"].get("status") == "FAILED"
                and any(
                    e["event_type"] == "run.failed"
                    and e["payload"].get("code") == "OUTPUT_GUARDRAIL_TRIPPED"
                    for e in cases["output_trip"]["events"]
                ),
                "output_tripwire_partial_history_rolled_back": metadata["output_trip"].get("turn_count") == 1
                and metadata["output_trip"].get("item_count") == 2
                and metadata["output_trip"].get("active_run_id") is None,
                "later_success_received_only_committed_history": len(captured["history_before"]) == 4
                and len(captured["history_before"][3]) == 2
                and MARKER in json.dumps(captured["history_before"][3], ensure_ascii=False)
                and "BLOCK_INPUT" not in json.dumps(captured["history_before"][3], ensure_ascii=False)
                and "BLOCK_OUTPUT" not in json.dumps(captured["history_before"][3], ensure_ascii=False),
                "second_success_committed_exactly_two_more_items": metadata["clean_2"].get("turn_count") == 2
                and metadata["clean_2"].get("item_count") == 4
                and metadata["clean_2"].get("active_run_id") is None,
                "guardrail_execution_counts_exact": counters["guardrail_runs"]
                == {"INPUT": 4, "OUTPUT": 3},
                "one_safe_tripwire_event_per_rejection": len(tripwire_events["input_trip"]) == 1
                and len(tripwire_events["output_trip"]) == 1
                and not tripwire_events["clean_1"]
                and not tripwire_events["clean_2"],
                "tripwire_metadata_safe": all(
                    set(event["payload"]) == {
                        "guardrail_id",
                        "guardrail_kind",
                        "tool_id",
                        "behavior",
                        "tripwire_triggered",
                        "guarded_content_persisted",
                        "output_info_persisted",
                        "raw_sdk_error_persisted",
                    }
                    and event["payload"].get("tool_id") is None
                    and event["payload"].get("guarded_content_persisted") is False
                    and event["payload"].get("output_info_persisted") is False
                    and event["payload"].get("raw_sdk_error_persisted") is False
                    for event in tripwire_events["input_trip"] + tripwire_events["output_trip"]
                ),
                "successful_turn_event_pairs_exact": len(started_events) == 4
                and len(completed_events) == 2
                and [e["payload"].get("item_count") for e in completed_events] == [2, 4],
                "rejected_runs_created_no_artifact": all(
                    not any(e["event_type"] == "artifact.created" for e in cases[name]["events"])
                    for name in ("input_trip", "output_trip")
                ),
                "two_successful_artifacts_only": artifact.get("content", {}).get("status") == "PASS"
                and MARKER in artifact.get("content", {}).get("summary", "")
                and final_counts["artifacts"] == 2,
                "recorded_evaluation_passed": evaluation_response.status_code == 201
                and evaluation.get("state") == "PASSED"
                and evaluation.get("case_id") == "sqlite-session-native-guardrail-v1",
                "all_root_invocations_terminal": all(
                    len(case["invocations"]) == 1
                    and case["invocations"][0]["state"] in {"SUCCEEDED", "FAILED"}
                    and case["invocations"][0]["workspace_access"] == "none"
                    for case in cases.values()
                ),
                "confirmation_replay_no_duplicate": replay_response.status_code in {200, 202}
                and replay.get("run_id") == clean_2["confirmed"].get("run_id")
                and replay.get("scheduled") is False
                and replay.get("replayed") is True,
                "clear_rejected_while_turn_lease_held": clear_pending.status_code == 409,
                "competing_turn_rejected_while_lease_held": competing_rejected is True,
                "failed_exclusivity_probe_did_not_commit_turn": final_session.get("turn_count") == 2
                and final_session.get("item_count") == 4
                and final_session.get("active_run_id") is None,
                "sdk_history_contains_only_two_successful_turns": len(history_items) == 4
                and MARKER in json.dumps(history_items, ensure_ascii=False)
                and "BLOCK_INPUT" not in json.dumps(history_items, ensure_ascii=False)
                and "BLOCK_OUTPUT" not in json.dumps(history_items, ensure_ascii=False),
                "raw_session_and_guarded_content_not_in_product_events": MARKER not in event_text
                and all(value not in event_text for value in REQUESTS.values()),
                "raw_requests_and_api_key_not_in_product_or_evaluation_db": all(
                    value not in product_text and value not in evaluation_text
                    for value in REQUESTS.values()
                )
                and MARKER not in product_text
                and MARKER not in evaluation_text
                and HIDDEN_API_KEY not in product_text
                and HIDDEN_API_KEY not in evaluation_text,
                "payload_retention_exact": cases["clean_1"]["submission"].get("payload_retention_state") == "DELETED"
                and cases["clean_2"]["submission"].get("payload_retention_state") == "DELETED"
                and cases["input_trip"]["submission"].get("payload_retention_state") == "RETAINED"
                and cases["output_trip"]["submission"].get("payload_retention_state") == "RETAINED"
                and len(list(payload_root.glob("payload_*.json"))) == 2,
                "session_handles_closed": counters["session_instances"] == counters["session_closes"],
                "final_product_counts_exact": final_counts
                == {
                    "tasks": 4,
                    "runs": 4,
                    "submissions": 4,
                    "invocations": 4,
                    "events": 43,
                    "artifacts": 2,
                    "evaluations": 1,
                },
                "references_unchanged": references_before == references_after,
                "cleanup_completed": True,
            }
            payload = {
                "schema_version": "okcanvas-step048-acceptance-v1",
                "state": "PASSED" if all(checks.values()) else "FAILED",
                "checks": checks,
                "session": {
                    "session_id": session_id,
                    "runtime_binding_sha256": binding.runtime_binding_sha256,
                    "after_clean_1": metadata["clean_1"],
                    "after_input_trip": metadata["input_trip"],
                    "after_output_trip": metadata["output_trip"],
                    "after_clean_2": metadata["clean_2"],
                    "final": final_session,
                    "history_item_count": len(history_items),
                },
                "cases": {
                    name: {
                        "run_id": case["confirmed"]["run_id"],
                        "status": case["terminal"].get("status"),
                        "event_count": len(case["events"]),
                        "tripwire_count": len(tripwire_events[name]),
                    }
                    for name, case in cases.items()
                },
                "gateway_counts": counters,
                "final_counts": final_counts,
                "protected_payload_file_count": len(list(payload_root.glob("payload_*.json"))),
                "evaluation": evaluation,
                "replay": replay,
            }
            final = workspace.finalize(payload)
            final["checks"]["cleanup_completed"] = (
                final["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
            )
            final["state"] = "PASSED" if all(final["checks"].values()) else "FAILED"
            output.parent.mkdir(parents=True, exist_ok=True)
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
        default=ROOT / "docs/evidence/STEP048_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
