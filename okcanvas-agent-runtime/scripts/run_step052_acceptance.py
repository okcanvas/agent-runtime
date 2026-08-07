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
from okcanvas_agent_runtime.agent.model.retry import ModelRetryPolicyCatalog
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ADMIN_KEY = "step052-local-admin-key"
SUBMITTER_KEY = "step052-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
ADMIN_HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
SUBMIT_HEADERS = {**ADMIN_HEADERS, "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY}
MODEL = "deterministic-step052-model"
FAIL_REQUEST = "NETWORK_FAILURE must fail once without any model retry."
SUCCESS_REQUEST = "Execute once through the immutable zero-retry OpenAI route."
HIDDEN_API_KEY = "step052-hidden-api-key"


def _usage():
    return SimpleNamespace(
        requests=1,
        input_tokens=17,
        output_tokens=6,
        total_tokens=23,
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
        "model_attempts": 0,
        "retry_policy_calls": 0,
    }
    captured: dict[str, object] = {
        "provider_kwargs": [],
        "client_kwargs": [],
        "requested_models": [],
        "run_config_models": [],
        "run_config_retry_max_retries": [],
        "retry_policy_decisions": [],
        "trace_sensitive_values": [],
    }
    previous_agents = sys.modules.get("agents")
    previous_openai = sys.modules.get("openai")
    previous_version = importlib.metadata.version
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"
    fake_openai = types.ModuleType("openai")

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            counters["openai_client_constructed"] += 1
            captured["client_kwargs"].append(dict(kwargs))

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

    class FakeModelRetrySettings:
        def __init__(self, **kwargs):
            self.max_retries = kwargs.get("max_retries")
            self.policy = kwargs.get("policy")

    class FakeRetryPolicies:
        @staticmethod
        def never():
            def policy(_context):
                counters["retry_policy_calls"] += 1
                captured["retry_policy_decisions"].append(False)
                return False

            return policy

    class FakeModelSettings:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

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
        summary="One model attempt completed under the immutable zero-retry policy.",
        findings=[],
        unverified=[],
    )

    class FakeResult:
        def __init__(self, *, agent, hooks, fail: bool):
            self.agent = agent
            self.hooks = hooks
            self.fail = fail
            self.context_wrapper = SimpleNamespace(usage=_usage())
            self.last_response_id = "resp-step052"

        async def stream_events(self):
            await self.hooks.on_agent_start(SimpleNamespace(), self.agent)
            await self.hooks.on_llm_start(
                SimpleNamespace(), self.agent, self.agent.instructions, [{"role": "user"}]
            )
            counters["model_attempts"] += 1
            if self.fail:
                raise RuntimeError("simulated network error before any response event")
            response = SimpleNamespace(
                response_id="resp-step052", request_id="req-step052", output=[1]
            )
            await self.hooks.on_llm_end(SimpleNamespace(), self.agent, response)
            await self.hooks.on_agent_end(SimpleNamespace(), self.agent, output)
            if False:
                yield None

        def final_output_as(self, output_type, raise_if_incorrect_type=False):
            assert not self.fail
            assert output_type is CodingAgentResult
            assert raise_if_incorrect_type is True
            return output

    class FakeRunner:
        @classmethod
        async def run(cls, *args, **kwargs):
            counters["runner_run"] += 1
            raise AssertionError("STEP052 must use Runner.run_streamed")

        @classmethod
        def run_streamed(cls, agent, request, **kwargs):
            counters["runner_run_streamed"] += 1
            values = kwargs["run_config"].values
            provider = values["model_provider"]
            selected_model = values["model"]
            retry = values["model_settings"].retry
            captured["run_config_models"].append(selected_model)
            captured["run_config_retry_max_retries"].append(retry.max_retries)
            captured["trace_sensitive_values"].append(values["trace_include_sensitive_data"])
            resolved = provider.get_model(selected_model)
            assert resolved.model_name == MODEL
            if "NETWORK_FAILURE" in request:
                decision = retry.policy(
                    SimpleNamespace(
                        attempt=1,
                        max_retries=retry.max_retries,
                        stream=True,
                        normalized=SimpleNamespace(
                            is_network_error=True,
                            is_timeout=False,
                            is_abort=False,
                        ),
                    )
                )
                assert decision is False
            return FakeResult(agent=agent, hooks=kwargs["hooks"], fail="NETWORK_FAILURE" in request)

    fake_agents.Agent = FakeAgent
    fake_agents.ModelRetrySettings = FakeModelRetrySettings
    fake_agents.ModelSettings = FakeModelSettings
    fake_agents.retry_policies = FakeRetryPolicies()
    fake_agents.OpenAIProvider = FakeOpenAIProvider
    fake_agents.RunConfig = FakeRunConfig
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_agents.gen_trace_id = lambda: "trace-step052"
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
    raise RuntimeError("STEP052 Run did not become terminal")


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


def _submit_and_confirm(client: TestClient, *, request: str, key: str) -> tuple[dict, dict]:
    response = client.post(
        "/v1/run-submissions/preflight",
        headers=SUBMIT_HEADERS,
        json={
            "agent_definition_id": "coding-agent",
            "input": request,
            "model": MODEL,
            "idempotency_key": key,
        },
    )
    response.raise_for_status()
    preflight = response.json()
    confirmed_response = client.post(
        f"/v1/run-submissions/{preflight['submission_id']}/confirm",
        headers=SUBMIT_HEADERS,
        json={"confirmation": preflight["confirmation_challenge"]},
    )
    confirmed_response.raise_for_status()
    return preflight, confirmed_response.json()


def run_acceptance(output: Path) -> int:
    references_before = {
        item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()
    }
    counters, captured, previous_agents, previous_openai, previous_version = _install_fakes()
    previous_key = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = HIDDEN_API_KEY
    try:
        with AcceptanceWorkspace(step_id="STEP052", output=output) as workspace:
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
                fail_preflight, fail_confirmed = _submit_and_confirm(
                    client, request=FAIL_REQUEST, key="step052-fail-0001"
                )
                failed = _wait_terminal(client, fail_confirmed["run_id"])
                failed_events = client.get(
                    f"/v1/runs/{fail_confirmed['run_id']}/events", headers=ADMIN_HEADERS
                ).json()["events"]

                success_preflight, success_confirmed = _submit_and_confirm(
                    client, request=SUCCESS_REQUEST, key="step052-success-0001"
                )
                succeeded = _wait_terminal(client, success_confirmed["run_id"])
                success_events = client.get(
                    f"/v1/runs/{success_confirmed['run_id']}/events", headers=ADMIN_HEADERS
                ).json()["events"]
                artifact = client.get(
                    f"/v1/runs/{success_confirmed['run_id']}/artifact", headers=ADMIN_HEADERS
                ).json()
                evaluation_response = client.post(
                    f"/v1/runs/{success_confirmed['run_id']}/evaluations",
                    headers=ADMIN_HEADERS,
                    json={"case_id": "immutable-openai-zero-retry-v1"},
                )
                evaluation = evaluation_response.json()
                replay_response = client.post(
                    f"/v1/run-submissions/{success_preflight['submission_id']}/confirm",
                    headers=SUBMIT_HEADERS,
                    json={"confirmation": success_preflight["confirmation_challenge"]},
                )
                replay = replay_response.json()

                drift_response = client.post(
                    "/v1/run-submissions/preflight",
                    headers=SUBMIT_HEADERS,
                    json={
                        "agent_definition_id": "coding-agent",
                        "input": "Retry policy drift must block confirmation.",
                        "model": MODEL,
                        "idempotency_key": "step052-drift-0001",
                    },
                )
                drift_response.raise_for_status()
                drift = drift_response.json()
                retry_path = project_root / "specs/runtime/model-retry-policy.json"
                original_retry = retry_path.read_text(encoding="utf-8")
                changed = json.loads(original_retry)
                changed["version"] = "1.0.1-drift"
                retry_path.write_text(
                    json.dumps(changed, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                drift_confirmation = client.post(
                    f"/v1/run-submissions/{drift['submission_id']}/confirm",
                    headers=SUBMIT_HEADERS,
                    json={"confirmation": drift["confirmation_challenge"]},
                )
                retry_path.write_text(original_retry, encoding="utf-8")

            definition = AgentDefinitionCatalog(project_root).resolve("coding-agent")
            binding = AgentRuntimeBindingCatalog(project_root).resolve(definition)
            retry_policy = ModelRetryPolicyCatalog(project_root).resolve()
            all_events = [*failed_events, *success_events]
            model_events = [e for e in all_events if e["event_type"] == "model.started"]
            event_text = json.dumps(all_events, ensure_ascii=False)
            product_text = product_db.read_bytes().decode("utf-8", errors="ignore")
            evaluation_text = evaluation_db.read_bytes().decode("utf-8", errors="ignore")
            final_counts = _counts(product_db, evaluation_db)
            references_after = {
                item.reference_id: item.to_dict()
                for item in ReferenceCatalogService(ROOT).verify_all()
            }
            client_kwargs = captured["client_kwargs"]
            provider_kwargs = captured["provider_kwargs"]
            checks = {
                "exact_zero_retry_policy_bound": binding.model_retry_policy["policy_sha256"]
                == retry_policy.policy_sha256
                and len(binding.model_retry_runtime_sha256) == 64,
                "runner_managed_retry_budget_zero": captured[
                    "run_config_retry_max_retries"
                ] == [0, 0]
                and retry_policy.runner_managed_max_retries == 0,
                "provider_managed_retry_budget_zero": len(client_kwargs) == 2
                and all(item.get("max_retries") == 0 for item in client_kwargs)
                and retry_policy.provider_managed_max_retries == 0,
                "official_openai_base_url_still_forced": all(
                    item.get("base_url") == "https://api.openai.com/v1" for item in client_kwargs
                ),
                "responses_http_and_strict_validation_preserved": len(provider_kwargs) == 2
                and all(item.get("use_responses") is True for item in provider_kwargs)
                and all(item.get("use_responses_websocket") is False for item in provider_kwargs)
                and all(item.get("strict_feature_validation") is True for item in provider_kwargs),
                "no_retry_policy_returns_false_for_network_failure": counters[
                    "retry_policy_calls"
                ] == 1
                and captured["retry_policy_decisions"] == [False],
                "retryable_categories_empty": retry_policy.retryable_categories == (),
                "conversation_locked_compatibility_retry_disabled": retry_policy.conversation_locked_compatibility_retries
                is False,
                "failed_run_attempted_model_exactly_once": failed.get("status") == "FAILED"
                and counters["model_attempts"] == 2,
                "successful_run_attempted_model_exactly_once": succeeded.get("status")
                == "SUCCEEDED",
                "runner_and_provider_counts_exact": counters["runner_run"] == 0
                and counters["runner_run_streamed"] == 2
                and counters["provider_constructed"] == 2
                and counters["provider_get_model"] == 2
                and counters["openai_client_constructed"] == 2
                and counters["provider_closed"] == 2,
                "failed_run_created_no_artifact": all(
                    e["event_type"] != "artifact.created" for e in failed_events
                ),
                "successful_artifact_verified": artifact.get("content", {}).get("status")
                == "PASS",
                "recorded_evaluation_passed": evaluation_response.status_code == 201
                and evaluation.get("state") == "PASSED",
                "confirmation_replay_no_duplicate": replay_response.status_code in {200, 202}
                and replay.get("replayed") is True
                and replay.get("scheduled") is False,
                "retry_policy_drift_blocked_confirmation": drift_confirmation.status_code == 409,
                "retry_policy_drift_created_no_third_task_or_run": final_counts["tasks"] == 2
                and final_counts["runs"] == 2,
                "model_events_expose_safe_zero_retry_identity": len(model_events) == 2
                and all(
                    e["payload"].get("model_retry_policy_id")
                    == "local-openai-zero-retry-v1"
                    and e["payload"].get("runner_managed_max_retries") == 0
                    and e["payload"].get("provider_managed_max_retries") == 0
                    for e in model_events
                ),
                "model_events_contain_no_endpoint_secret_or_raw_error": "base_url"
                not in event_text
                and HIDDEN_API_KEY not in event_text
                and "simulated network error" not in event_text,
                "failed_and_drift_payloads_retained_success_deleted": len(
                    list(payload_root.glob("payload_*.json"))
                )
                == 2,
                "raw_requests_and_api_key_not_in_product_or_evaluation_db": FAIL_REQUEST
                not in product_text
                and SUCCESS_REQUEST not in product_text
                and FAIL_REQUEST not in evaluation_text
                and SUCCESS_REQUEST not in evaluation_text
                and HIDDEN_API_KEY not in product_text
                and HIDDEN_API_KEY not in evaluation_text,
                "all_root_invocations_terminal": final_counts["invocations"] == 2,
                "final_product_counts_exact": final_counts
                == {
                    "tasks": 2,
                    "runs": 2,
                    "submissions": 3,
                    "invocations": 2,
                    "events": 18,
                    "artifacts": 1,
                    "evaluations": 1,
                },
                "references_unchanged": references_before == references_after,
                "cleanup_completed": True,
            }
            report = {
                "schema_version": "okcanvas-step052-acceptance-v1",
                "state": "PASSED" if all(checks.values()) else "FAILED",
                "checks": checks,
                "retry_policy": retry_policy.to_binding_dict(),
                "gateway_counts": counters,
                "run_event_counts": {
                    "failed": len(failed_events),
                    "succeeded": len(success_events),
                    "total": len(all_events),
                },
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/evidence/STEP052_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
