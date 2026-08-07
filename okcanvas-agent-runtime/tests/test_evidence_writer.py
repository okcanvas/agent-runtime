import asyncio
import json
from pathlib import Path

from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.adapters.evidence import write_run_evidence
from okcanvas_agent_runtime.adapters.openai.runtime.service import AgentRuntimeService


class NeverCalledGateway:
    async def run(self, **kwargs):
        raise AssertionError("gateway must not be called")


def test_atomic_evidence_writer(tmp_path: Path) -> None:
    envelope = asyncio.run(
        AgentRuntimeService(NeverCalledGateway()).run(
            request="request",
            settings=RuntimeSettings(model="model", api_key="secret"),
            live_opt_in=False,
        )
    )
    target = tmp_path / "nested" / "run.json"
    write_run_evidence(target, envelope)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["run_id"].startswith("run_")
    assert payload["state"] == "FAILED"
    assert "secret" not in target.read_text(encoding="utf-8")
    assert list(target.parent.glob("*.tmp")) == []
