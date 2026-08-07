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
from okcanvas_agent_runtime.agent.model.provider_identity import ProviderIdentifierPolicyCatalog
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ADMIN_KEY = "step055-local-admin-key"
SUBMITTER_KEY = "step055-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
ADMIN_HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
SUBMIT_HEADERS = {**ADMIN_HEADERS, "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY}
MODEL = "deterministic-step055-model"
REQUEST = "Return a safe final answer while minimizing provider response and request identifiers."
HIDDEN_API_KEY = "step055-hidden-api-key"
PROVIDER_RESPONSE_ID = "resp-step055-private-provider-identifier"
PROVIDER_REQUEST_ID = "req-step055-private-provider-identifier"
REASONING_SUMMARY_SENTINEL = "STEP055-PRIVATE-REASONING-SUMMARY"
REASONING_CONTENT_SENTINEL = "STEP055-PRIVATE-REASONING-CONTENT"
REASONING_ENCRYPTED_SENTINEL = "STEP055-ENCRYPTED-REASONING"
REASONING_PROVIDER_SENTINEL = "STEP055-PROVIDER-DATA"
REASONING_ITEM_ID = "rs_step055_private"


def _usage():
    return SimpleNamespace(
        requests=1,
        input_tokens=19,
        output_tokens=18,
        total_tokens=37,
        input_tokens_details=SimpleNamespace(cached_tokens=0),
        output_tokens_details=SimpleNamespace(reasoning_tokens=11),
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
        "run_config_reasoning": [],
        "run_config_response_include": [],
        "run_config_store": [],
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
        summary="Safe output completed with provider identifiers minimized.",
        findings=[],
        unverified=[],
    )

    class FakeResult:
        def __init__(self, *, agent, hooks):
            self.agent = agent
            self.hooks = hooks
            self.context_wrapper = SimpleNamespace(usage=_usage())
            self.last_response_id = PROVIDER_RESPONSE_ID

        async def stream_events(self):
            await self.hooks.on_agent_start(SimpleNamespace(), self.agent)
            await self.hooks.on_llm_start(
                SimpleNamespace(), self.agent, self.agent.instructions, [{"role": "user"}]
            )
            reasoning_item = SimpleNamespace(
                type="reasoning",
                id=REASONING_ITEM_ID,
                summary=[SimpleNamespace(text=REASONING_SUMMARY_SENTINEL)],
                content=[SimpleNamespace(text=REASONING_CONTENT_SENTINEL)],
                encrypted_content=REASONING_ENCRYPTED_SENTINEL,
                provider_data={"private": REASONING_PROVIDER_SENTINEL},
            )
            response = SimpleNamespace(
                response_id=PROVIDER_RESPONSE_ID,
                request_id=PROVIDER_REQUEST_ID,
                output=[reasoning_item, SimpleNamespace(type="message")],
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
            raise AssertionError("STEP055 must use Runner.run_streamed")

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
            model_settings = values["model_settings"]
            captured["run_config_reasoning"].append(getattr(model_settings, "reasoning", "missing"))
            captured["run_config_response_include"].append(
                getattr(model_settings, "response_include", "missing")
            )
            captured["run_config_store"].append(getattr(model_settings, "store", "missing"))
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
    fake_agents.gen_trace_id = lambda: "trace-step055"
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
    raise RuntimeError("STEP055 Run did not become terminal")


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
        with AcceptanceWorkspace(step_id="STEP055", output=output) as workspace:
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
                        "idempotency_key": "step055-denied-route-0001",
                    },
                )
                preflight_response = client.post(
                    "/v1/run-submissions/preflight",
                    headers=SUBMIT_HEADERS,
                    json={
                        "agent_definition_id": "coding-agent",
                        "input": REQUEST,
                        "model": MODEL,
                        "idempotency_key": "step055-success-0001",
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
                    json={"case_id": "immutable-openai-provider-identifier-minimization-v1"},
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
                        "input": "Provider identifier policy drift must block confirmation before Product state.",
                        "model": MODEL,
                        "idempotency_key": "step055-policy-drift-0001",
                    },
                )
                drift_preflight_response.raise_for_status()
                drift_preflight = drift_preflight_response.json()
                policy_path = project_root / "specs/runtime/openai-provider-identifier-policy.json"
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
            policy = ProviderIdentifierPolicyCatalog(project_root).resolve()
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
            completed_events = [e for e in events if e["event_type"] == "model.completed"]
            run_completed = [e for e in events if e["event_type"] == "run.completed"]
            artifact_text = json.dumps(artifact, ensure_ascii=False)
            sensitive_values = (
                REASONING_SUMMARY_SENTINEL,
                REASONING_CONTENT_SENTINEL,
                REASONING_ENCRYPTED_SENTINEL,
                REASONING_PROVIDER_SENTINEL,
                REASONING_ITEM_ID,
            )
            checks = {
                "provider_prefixed_model_rejected_before_preflight_persistence": denied.status_code == 422,
                "allowed_model_preflight_bound_exact_runtime": preflight.get("model") == MODEL
                and preflight.get("runtime_binding_sha256") == binding.runtime_binding_sha256,
                "exact_provider_identifier_policy_bound": (
                    binding.provider_identifier_policy["policy_sha256"] == policy.policy_sha256
                    and len(binding.provider_identifier_runtime_sha256) == 64
                ),
                "provider_response_and_request_id_persistence_disabled": (
                    policy.persist_response_id is False
                    and policy.persist_request_id is False
                ),
                "provider_identifier_presence_only_enabled": policy.persist_identifier_presence is True,
                "root_run_config_explicit_model_and_provider_used": (
                    captured["run_config_models"] == [MODEL]
                    and captured["run_config_provider_ids"] == ["openai"]
                ),
                "sdk_openai_provider_constructed_once": counters["provider_constructed"] == 1
                and counters["openai_client_constructed"] == 1,
                "official_openai_route_preserved": len(client_kwargs) == 1
                and client_kwargs[0].get("base_url") == "https://api.openai.com/v1"
                and client_kwargs[0].get("max_retries") == 0
                and provider_kwargs[0].get("use_responses") is True
                and provider_kwargs[0].get("use_responses_websocket") is False
                and provider_kwargs[0].get("strict_feature_validation") is True,
                "selected_model_resolved_exactly_once": counters["provider_get_model"] == 1
                and captured["requested_models"] == [MODEL],
                "zero_retry_policy_preserved": (
                    completed_events
                    and model_events[0]["payload"].get("runner_managed_max_retries") == 0
                    and model_events[0]["payload"].get("provider_managed_max_retries") == 0
                ),
                "reasoning_minimization_request_preserved": (
                    captured["run_config_reasoning"] == [None]
                    and captured["run_config_response_include"] == [[]]
                ),
                "response_storage_disabled_preserved": captured["run_config_store"] == [False],
                "sensitive_trace_data_disabled": captured["trace_sensitive_values"] == [False],
                "provider_closed_exactly_once": counters["provider_closed"] == 1,
                "governed_run_succeeded": terminal.get("status") == "SUCCEEDED"
                and counters["runner_run"] == 0
                and counters["runner_run_streamed"] == 1,
                "model_started_identifier_policy_metadata_exact": len(model_events) == 1
                and model_events[0]["payload"].get("provider_identifier_policy_id")
                == "local-openai-provider-identifier-minimization-v1"
                and model_events[0]["payload"].get("provider_identifier_policy_sha256")
                == policy.policy_sha256
                and model_events[0]["payload"].get("provider_response_id_persisted") is False
                and model_events[0]["payload"].get("provider_request_id_persisted") is False
                and model_events[0]["payload"].get("provider_identifier_presence_persisted") is True,
                "model_completed_identifier_presence_exact": len(completed_events) == 1
                and completed_events[0]["payload"].get("response_id_present") is True
                and completed_events[0]["payload"].get("request_id_present") is True
                and completed_events[0]["payload"].get("provider_response_id_persisted") is False
                and completed_events[0]["payload"].get("provider_request_id_persisted") is False,
                "model_completed_contains_no_raw_identifier_fields": len(completed_events) == 1
                and "response_id" not in completed_events[0]["payload"]
                and "request_id" not in completed_events[0]["payload"],
                "provider_identifiers_absent_from_events": PROVIDER_RESPONSE_ID not in event_text
                and PROVIDER_REQUEST_ID not in event_text,
                "provider_identifiers_absent_from_product_and_evaluation_db": (
                    PROVIDER_RESPONSE_ID not in product_text
                    and PROVIDER_REQUEST_ID not in product_text
                    and PROVIDER_RESPONSE_ID not in evaluation_text
                    and PROVIDER_REQUEST_ID not in evaluation_text
                ),
                "provider_identifiers_absent_from_artifact": PROVIDER_RESPONSE_ID not in artifact_text
                and PROVIDER_REQUEST_ID not in artifact_text,
                "run_completion_response_id_minimized": len(run_completed) == 1
                and run_completed[0]["payload"].get("response_id") is None,
                "prior_reasoning_private_fields_absent": all(
                    value not in event_text
                    and value not in product_text
                    and value not in evaluation_text
                    and value not in artifact_text
                    for value in sensitive_values
                ),
                "reasoning_token_count_preserved": len(run_completed) == 1
                and run_completed[0]["payload"].get("usage", {}).get("reasoning_tokens") == 11,
                "artifact_verified": artifact.get("content", {}).get("status") == "PASS",
                "recorded_evaluation_passed": evaluation_response.status_code == 201
                and evaluation.get("state") == "PASSED",
                "confirmation_replay_no_duplicate": replay_response.status_code in {200, 202}
                and replay.get("replayed") is True
                and replay.get("scheduled") is False,
                "provider_identifier_policy_drift_blocked_confirmation": drift_confirmation.status_code == 409,
                "provider_identifier_policy_drift_created_no_second_task_or_run": final_counts["tasks"] == 1
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
                "runtime_binding_contains_no_secret_endpoint_or_provider_id": HIDDEN_API_KEY
                not in json.dumps(binding.to_fingerprint_dict(), ensure_ascii=False)
                and "untrusted.invalid"
                not in json.dumps(binding.to_fingerprint_dict(), ensure_ascii=False)
                and PROVIDER_RESPONSE_ID
                not in json.dumps(binding.to_fingerprint_dict(), ensure_ascii=False)
                and PROVIDER_REQUEST_ID
                not in json.dumps(binding.to_fingerprint_dict(), ensure_ascii=False),
                "references_unchanged": references_before == references_after,
                "cleanup_completed": True,
            }
            report = {
                "schema_version": "okcanvas-step055-acceptance-v1",
                "state": "PASSED" if all(checks.values()) else "FAILED",
                "checks": checks,
                "provider_identifier_policy": {
                    **policy.to_binding_dict(),
                    "runtime_binding_sha256": binding.runtime_binding_sha256,
                    "runtime_source_sha256": binding.provider_identifier_runtime_sha256,
                    "observed_response_id_present": completed_events[0]["payload"].get("response_id_present") if completed_events else None,
                    "observed_request_id_present": completed_events[0]["payload"].get("request_id_present") if completed_events else None,
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
        default=ROOT / "docs/evidence/STEP055_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
