from __future__ import annotations

import argparse
import base64
import importlib.metadata
import json
import os
import shutil
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
from okcanvas_agent_runtime.agent.model.routing import ModelRoutingPolicyCatalog
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ADMIN_KEY = "step051-local-admin-key"
SUBMITTER_KEY = "step051-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
ADMIN_HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
SUBMIT_HEADERS = {**ADMIN_HEADERS, "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY}
MODEL = "deterministic-step051-model"
REQUEST = "Execute through the immutable OpenAI Responses HTTP model route."
HIDDEN_API_KEY = "step051-hidden-api-key"


def _usage():
    return SimpleNamespace(
        requests=1,
        input_tokens=19,
        output_tokens=7,
        total_tokens=26,
        input_tokens_details=SimpleNamespace(cached_tokens=0),
        output_tokens_details=SimpleNamespace(reasoning_tokens=0),
    )


def _install_fakes():
    counters = {
        "runner_run": 0,
        "runner_run_streamed": 0,
        "provider_constructed": 0,
        "provider_get_model": 0,
        "provider_closed": 0,
        "openai_client_constructed": 0,
    }
    captured: dict[str, object] = {
        "provider_kwargs": [],
        "client_kwargs": [],
        "requested_models": [],
        "run_config_models": [],
        "run_config_provider_ids": [],
        "trace_sensitive_values": [],
    }
    previous_agents = sys.modules.get("agents")
    previous_openai = sys.modules.get("openai")
    previous_version = importlib.metadata.version
    fake_agents = types.ModuleType("agents")
    fake_openai = types.ModuleType("openai")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"


    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            counters["openai_client_constructed"] += 1
            captured["client_kwargs"].append(dict(kwargs))

    class FakeModelRetrySettings:
        def __init__(self, **kwargs):
            self.max_retries = kwargs.get("max_retries")
            self.policy = kwargs.get("policy")

    class FakeRetryPolicies:
        @staticmethod
        def never():
            return lambda _context: False

    class FakeModelSettings:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeOpenAIProvider:
        def __init__(self, **kwargs):
            counters["provider_constructed"] += 1
            captured["provider_kwargs"].append(dict(kwargs))
            self.closed = False

        def get_model(self, model_name):
            counters["provider_get_model"] += 1
            captured["requested_models"].append(model_name)
            return SimpleNamespace(model_name=model_name)

        async def aclose(self):
            if not self.closed:
                self.closed = True
                counters["provider_closed"] += 1

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
        status=AgentStatus.PASS,
        summary="Immutable OpenAI Responses HTTP route completed without fallback.",
        findings=[],
        unverified=[],
    )

    class FakeResult:
        def __init__(self, *, agent, hooks):
            self.agent = agent
            self.hooks = hooks
            self.context_wrapper = SimpleNamespace(usage=_usage())
            self.last_response_id = "resp-step051"

        async def stream_events(self):
            await self.hooks.on_agent_start(SimpleNamespace(), self.agent)
            await self.hooks.on_llm_start(
                SimpleNamespace(), self.agent, self.agent.instructions, [{"role": "user"}]
            )
            response = SimpleNamespace(
                response_id="resp-step051", request_id="req-step051", output=[1]
            )
            await self.hooks.on_llm_end(SimpleNamespace(), self.agent, response)
            await self.hooks.on_agent_end(SimpleNamespace(), self.agent, output)
            if False:
                yield None

        def final_output_as(self, output_type, raise_if_incorrect_type=False):
            assert output_type is CodingAgentResult
            assert raise_if_incorrect_type is True
            return output

    class FakeRunner:
        @classmethod
        async def run(cls, *args, **kwargs):
            counters["runner_run"] += 1
            raise AssertionError("STEP051 must use Runner.run_streamed")

        @classmethod
        def run_streamed(cls, agent, request, **kwargs):
            counters["runner_run_streamed"] += 1
            run_config = kwargs["run_config"]
            values = run_config.values
            provider = values["model_provider"]
            selected_model = values["model"]
            captured["run_config_models"].append(selected_model)
            captured["run_config_provider_ids"].append(provider.route.policy.provider_id)
            captured["trace_sensitive_values"].append(values["trace_include_sensitive_data"])
            resolved = provider.get_model(selected_model)
            assert resolved.model_name == MODEL
            return FakeResult(agent=agent, hooks=kwargs["hooks"])

    fake_agents.Agent = FakeAgent
    fake_agents.ModelRetrySettings = FakeModelRetrySettings
    fake_agents.ModelSettings = FakeModelSettings
    fake_agents.retry_policies = FakeRetryPolicies()
    fake_agents.OpenAIProvider = FakeOpenAIProvider
    fake_agents.RunConfig = FakeRunConfig
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_agents.gen_trace_id = lambda: "trace-step051"
    fake_agents.set_default_openai_key = lambda value: None
    fake_openai.AsyncOpenAI = FakeAsyncOpenAI
    sys.modules["agents"] = fake_agents
    sys.modules["openai"] = fake_openai
    importlib.metadata.version = (
        lambda name: "0.19.0" if name == "openai-agents" else previous_version(name)
    )
    return counters, captured, previous_agents, previous_openai, previous_version


def _restore(previous_agents, previous_openai, previous_version):
    importlib.metadata.version = previous_version
    if previous_agents is None:
        sys.modules.pop("agents", None)
    else:
        sys.modules["agents"] = previous_agents
    if previous_openai is None:
        sys.modules.pop("openai", None)
    else:
        sys.modules["openai"] = previous_openai


def _wait_terminal(client: TestClient, run_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        body = client.get(f"/v1/runs/{run_id}", headers=ADMIN_HEADERS).json()
        if body.get("status") in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return body
        time.sleep(0.02)
    raise RuntimeError("STEP051 Run did not become terminal")


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
            "invocations": product.execute(
                "select count(*) from agent_invocation"
            ).fetchone()[0],
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
    counters, captured, previous_agents, previous_openai, previous_version = _install_fakes()
    previous_key = os.environ.get("OPENAI_API_KEY")
    previous_base_url = os.environ.get("OPENAI_BASE_URL")
    os.environ["OPENAI_API_KEY"] = HIDDEN_API_KEY
    os.environ["OPENAI_BASE_URL"] = "https://untrusted.invalid/v1"
    try:
        with AcceptanceWorkspace(step_id="STEP051", output=output) as workspace:
            project_root = workspace.scratch_dir / "project"
            shutil.copytree(
                ROOT,
                project_root,
                ignore=shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache", "*.pyc"),
            )
            product_db = workspace.database_dir / "product.sqlite3"
            evaluation_db = workspace.database_dir / "evaluation.sqlite3"
            payload_root = workspace.scratch_dir / "payloads"
            app = create_app(
                project_root=project_root,
                product_db=product_db,
                artifact_root=workspace.artifact_dir,
                evaluation_db=evaluation_db,
                admin_key=ADMIN_KEY,
                run_submitter_key=SUBMITTER_KEY,
                protected_payload_root=payload_root,
                protected_payload_key=PAYLOAD_KEY,
            )
            with TestClient(app) as client:
                denied = client.post(
                    "/v1/run-submissions/preflight",
                    headers=SUBMIT_HEADERS,
                    json={
                        "agent_definition_id": "coding-agent",
                        "input": "This provider-prefixed route must be rejected.",
                        "model": "litellm/anthropic/claude",
                        "idempotency_key": "step051-denied-route-0001",
                    },
                )
                preflight_response = client.post(
                    "/v1/run-submissions/preflight",
                    headers=SUBMIT_HEADERS,
                    json={
                        "agent_definition_id": "coding-agent",
                        "input": REQUEST,
                        "model": MODEL,
                        "idempotency_key": "step051-success-0001",
                    },
                )
                preflight_response.raise_for_status()
                preflight = preflight_response.json()
                confirm_response = client.post(
                    f"/v1/run-submissions/{preflight['submission_id']}/confirm",
                    headers=SUBMIT_HEADERS,
                    json={"confirmation": preflight["confirmation_challenge"]},
                )
                confirm_response.raise_for_status()
                confirmed = confirm_response.json()
                terminal = _wait_terminal(client, confirmed["run_id"])
                events = client.get(
                    f"/v1/runs/{confirmed['run_id']}/events", headers=ADMIN_HEADERS
                ).json()["events"]
                artifact = client.get(
                    f"/v1/runs/{confirmed['run_id']}/artifact", headers=ADMIN_HEADERS
                ).json()
                evaluation_response = client.post(
                    f"/v1/runs/{confirmed['run_id']}/evaluations",
                    headers=ADMIN_HEADERS,
                    json={"case_id": "immutable-openai-model-route-v1"},
                )
                evaluation = evaluation_response.json()
                replay_response = client.post(
                    f"/v1/run-submissions/{preflight['submission_id']}/confirm",
                    headers=SUBMIT_HEADERS,
                    json={"confirmation": preflight["confirmation_challenge"]},
                )
                replay = replay_response.json()

                drift_preflight_response = client.post(
                    "/v1/run-submissions/preflight",
                    headers=SUBMIT_HEADERS,
                    json={
                        "agent_definition_id": "coding-agent",
                        "input": "Policy drift must block confirmation before Product state.",
                        "model": MODEL,
                        "idempotency_key": "step051-policy-drift-0001",
                    },
                )
                drift_preflight_response.raise_for_status()
                drift_preflight = drift_preflight_response.json()
                policy_path = project_root / "specs/runtime/model-routing-policy.json"
                original_policy = policy_path.read_text(encoding="utf-8")
                changed = json.loads(original_policy)
                changed["version"] = "1.0.1-drift"
                policy_path.write_text(
                    json.dumps(changed, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                drift_confirmation = client.post(
                    f"/v1/run-submissions/{drift_preflight['submission_id']}/confirm",
                    headers=SUBMIT_HEADERS,
                    json={"confirmation": drift_preflight["confirmation_challenge"]},
                )
                policy_path.write_text(original_policy, encoding="utf-8")

            definition = AgentDefinitionCatalog(project_root).resolve("coding-agent")
            binding = AgentRuntimeBindingCatalog(project_root).resolve(definition)
            policy = ModelRoutingPolicyCatalog(project_root).resolve()
            model_events = [e for e in events if e["event_type"] == "model.started"]
            event_text = json.dumps(events, ensure_ascii=False)
            product_text = product_db.read_bytes().decode("utf-8", errors="ignore")
            evaluation_text = evaluation_db.read_bytes().decode("utf-8", errors="ignore")
            final_counts = _counts(product_db, evaluation_db)
            references_after = {
                item.reference_id: item.to_dict()
                for item in ReferenceCatalogService(ROOT).verify_all()
            }
            provider_kwargs = captured["provider_kwargs"]
            client_kwargs = captured["client_kwargs"]
            checks = {
                "provider_prefixed_model_rejected_before_preflight_persistence": denied.status_code == 422,
                "allowed_model_preflight_bound_exact_runtime": preflight.get("model") == MODEL
                and preflight.get("runtime_binding_sha256") == binding.runtime_binding_sha256,
                "exact_product_model_policy_bound": binding.model_routing_policy["policy_sha256"]
                == policy.policy_sha256
                and len(binding.model_provider_runtime_sha256) == 64,
                "run_config_explicit_model_and_provider_used": captured["run_config_models"] == [MODEL]
                and captured["run_config_provider_ids"] == ["openai"],
                "sdk_openai_provider_constructed_once": counters["provider_constructed"] == 1
                and counters["openai_client_constructed"] == 1,
                "official_openai_base_url_forced": len(client_kwargs) == 1
                and client_kwargs[0].get("base_url") == "https://api.openai.com/v1"
                and client_kwargs[0].get("base_url") != os.environ["OPENAI_BASE_URL"],
                "responses_http_transport_forced": provider_kwargs[0].get("use_responses") is True
                and provider_kwargs[0].get("use_responses_websocket") is False,
                "strict_provider_feature_validation_enabled": provider_kwargs[0].get(
                    "strict_feature_validation"
                ) is True,
                "selected_model_resolved_exactly_once": counters["provider_get_model"] == 1
                and captured["requested_models"] == [MODEL],
                "automatic_fallback_absent": policy.automatic_fallback is False
                and policy.fallback_model_ids == (),
                "sensitive_trace_data_disabled": captured["trace_sensitive_values"] == [False],
                "provider_closed_exactly_once": counters["provider_closed"] == 1,
                "governed_run_succeeded": terminal.get("status") == "SUCCEEDED"
                and counters["runner_run"] == 0
                and counters["runner_run_streamed"] == 1,
                "model_event_route_metadata_exact": len(model_events) == 1
                and model_events[0]["payload"].get("model_route_id") == "openai:responses:http"
                and model_events[0]["payload"].get("provider_id") == "openai"
                and model_events[0]["payload"].get("automatic_fallback") is False,
                "model_event_contains_no_endpoint_or_secret": "base_url" not in event_text
                and HIDDEN_API_KEY not in event_text,
                "artifact_verified": artifact.get("content", {}).get("status") == "PASS",
                "recorded_evaluation_passed": evaluation_response.status_code == 201
                and evaluation.get("state") == "PASSED",
                "confirmation_replay_no_duplicate": replay_response.status_code in {200, 202}
                and replay.get("replayed") is True
                and replay.get("scheduled") is False,
                "policy_drift_blocked_confirmation": drift_confirmation.status_code == 409,
                "policy_drift_created_no_second_task_or_run": final_counts["tasks"] == 1
                and final_counts["runs"] == 1,
                "final_product_counts_exact": final_counts
                == {
                    "tasks": 1,
                    "runs": 1,
                    "submissions": 2,
                    "invocations": 1,
                    "events": 10,
                    "artifacts": 1,
                    "evaluations": 1,
                },
                "successful_payload_deleted_drift_payload_retained": len(
                    list(payload_root.glob("payload_*.json"))
                ) == 1,
                "raw_request_and_api_key_not_in_product_or_evaluation_db": REQUEST not in product_text
                and REQUEST not in evaluation_text
                and HIDDEN_API_KEY not in product_text
                and HIDDEN_API_KEY not in evaluation_text,
                "references_unchanged": references_before == references_after,
                "cleanup_completed": True,
            }
            report = {
                "schema_version": "okcanvas-step051-acceptance-v1",
                "state": "PASSED" if all(checks.values()) else "FAILED",
                "checks": checks,
                "route": {
                    "policy_id": policy.policy_id,
                    "version": policy.version,
                    "policy_sha256": policy.policy_sha256,
                    "route_id": policy.route_id,
                    "provider_id": policy.provider_id,
                    "api": policy.api,
                    "transport": policy.transport,
                    "selected_model": MODEL,
                    "automatic_fallback": policy.automatic_fallback,
                    "fallback_model_ids": list(policy.fallback_model_ids),
                    "runtime_binding_sha256": binding.runtime_binding_sha256,
                    "provider_runtime_sha256": binding.model_provider_runtime_sha256,
                },
                "gateway_counts": counters,
                "final_counts": final_counts,
                "protected_payload_file_count": len(list(payload_root.glob("payload_*.json"))),
                "evaluation": evaluation,
                "replay": replay,
                "drift_confirmation_status": drift_confirmation.status_code,
            }
            final = workspace.finalize(report)
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
        _restore(previous_agents, previous_openai, previous_version)
        if previous_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = previous_key
        if previous_base_url is None:
            os.environ.pop("OPENAI_BASE_URL", None)
        else:
            os.environ["OPENAI_BASE_URL"] = previous_base_url


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/evidence/STEP051_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
