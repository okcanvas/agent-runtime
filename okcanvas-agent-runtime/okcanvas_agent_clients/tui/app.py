from __future__ import annotations

import getpass
import hmac
import json
import os
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, TextIO

from okcanvas_agent_clients.tui.client import LocalTUIControlClient
from okcanvas_agent_clients.tui.config import TUIClientConfig, TUIClientError


TERMINAL_RUN_STATES = {"SUCCEEDED", "FAILED", "CANCELLED"}


class Terminal(Protocol):
    def write(self, value: str = "") -> None: ...

    def read(self, prompt: str) -> str: ...

    def read_secret(self, prompt: str) -> str: ...


class ConsoleTerminal:
    def __init__(self, *, output: TextIO | None = None) -> None:
        self._output = output or sys.stdout

    def write(self, value: str = "") -> None:
        print(value, file=self._output, flush=True)

    def read(self, prompt: str) -> str:
        return input(prompt)

    def read_secret(self, prompt: str) -> str:
        return getpass.getpass(prompt)


@dataclass(frozen=True)
class TUIRunOutcome:
    agent: dict[str, Any]
    preflight: dict[str, Any]
    confirmed: dict[str, Any]
    events: tuple[dict[str, Any], ...]
    run: dict[str, Any]
    invocations: tuple[dict[str, Any], ...]
    artifact: dict[str, Any]
    evaluation: dict[str, Any]


def is_foundation_compatible_agent(agent: dict[str, Any]) -> bool:
    return (
        agent.get("session_mode") == "disabled"
        and agent.get("workspace_access") == "none"
        and not agent.get("tools")
        and not agent.get("mcp_servers")
        and not agent.get("handoffs")
        and not agent.get("agent_tools")
        and not agent.get("guardrails")
    )


def compatible_agents(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (item for item in items if is_foundation_compatible_agent(item)),
        key=lambda item: str(item.get("agent_id") or ""),
    )


class GovernedTUIFlow:
    def __init__(self, client: LocalTUIControlClient) -> None:
        self._client = client

    def execute(
        self,
        *,
        agent_id: str,
        request: str,
        model: str | None,
        evaluation_case_id: str,
        confirmation_provider: Callable[[str], str],
        on_preflight: Callable[[dict[str, Any]], None] | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> TUIRunOutcome:
        agent = self._client.get_agent(agent_id)
        if not is_foundation_compatible_agent(agent):
            raise TUIClientError(
                "TUI_AGENT_NOT_SUPPORTED",
                "STEP056 TUI Foundation supports only tool-free, Session-disabled, workspace-free Agents",
            )
        normalized_request = request.strip()
        if not normalized_request:
            raise TUIClientError("TUI_REQUEST_INVALID", "A non-empty request is required")

        preflight = self._client.preflight(
            agent_definition_id=agent_id,
            request=normalized_request,
            model=model.strip() if model else None,
            idempotency_key=f"tui-{uuid.uuid4()}",
        )
        if preflight.get("approval_required") is not False or preflight.get("executable_now") is not True:
            raise TUIClientError(
                "TUI_PREFLIGHT_NOT_EXECUTABLE",
                "STEP056 TUI Foundation requires an immediately executable, non-approval preflight",
            )
        challenge = preflight.get("confirmation_challenge")
        if not isinstance(challenge, str) or not challenge:
            raise TUIClientError(
                "TUI_CONFIRMATION_CHALLENGE_MISSING",
                "Control API did not return an exact confirmation challenge",
            )
        if on_preflight is not None:
            on_preflight(preflight)
        typed = confirmation_provider(challenge)
        if not hmac.compare_digest(typed, challenge):
            raise TUIClientError(
                "TUI_CONFIRMATION_MISMATCH",
                "The exact governed Run confirmation is required",
            )

        confirmed = self._client.confirm(
            submission_id=str(preflight["submission_id"]),
            confirmation=typed,
        )
        run_id = str(confirmed.get("run_id") or "")
        if not run_id:
            raise TUIClientError("TUI_RESPONSE_INVALID", "Control API returned no Run ID")

        events: list[dict[str, Any]] = []
        for event in self._client.stream_events(run_id=run_id):
            if str(event.get("run_id") or "") != run_id:
                raise TUIClientError(
                    "TUI_SSE_RUN_ID_MISMATCH",
                    "Persisted SSE returned an Event for another Run",
                )
            events.append(event)
            if on_event is not None:
                on_event(event)

        run = self._client.get_run(run_id)
        if run.get("status") not in TERMINAL_RUN_STATES:
            raise TUIClientError(
                "TUI_RUN_NOT_TERMINAL",
                "Persisted SSE ended before the Run reached a terminal state",
            )
        if run.get("status") != "SUCCEEDED":
            raise TUIClientError(
                "TUI_RUN_FAILED",
                f"Governed Run ended in {run.get('status')}",
            )

        invocations = tuple(self._client.list_invocations(run_id))
        artifact = self._client.get_artifact(run_id)
        evaluation = self._client.evaluate_run(
            run_id=run_id,
            case_id=evaluation_case_id,
        )
        return TUIRunOutcome(
            agent=agent,
            preflight=preflight,
            confirmed=confirmed,
            events=tuple(events),
            run=run,
            invocations=invocations,
            artifact=artifact,
            evaluation=evaluation,
        )


class TUIApplication:
    def __init__(self, client: LocalTUIControlClient, terminal: Terminal | None = None) -> None:
        self._client = client
        self._terminal = terminal or ConsoleTerminal()

    def run_once(
        self,
        *,
        agent_id: str,
        request: str,
        model: str | None,
        evaluation_case_id: str,
        confirmation_provider: Callable[[str], str],
    ) -> TUIRunOutcome:
        self._render_header()
        health = self._client.health()
        self._terminal.write(
            f"Control API: {health.get('status')} · {health.get('version')} · loopback governed mode"
        )
        flow = GovernedTUIFlow(self._client)
        outcome = flow.execute(
            agent_id=agent_id,
            request=request,
            model=model,
            evaluation_case_id=evaluation_case_id,
            confirmation_provider=confirmation_provider,
            on_preflight=self._render_preflight,
            on_event=self._render_event,
        )
        self._render_outcome(outcome)
        return outcome

    def run_interactive(
        self,
        *,
        agent_id: str | None = None,
        model: str | None = None,
        evaluation_case_id: str | None = None,
    ) -> TUIRunOutcome:
        self._render_header()
        health = self._client.health()
        self._terminal.write(
            f"Control API: {health.get('status')} · {health.get('version')} · {health.get('mode')}"
        )
        agents = compatible_agents(self._client.list_agents())
        if not agents:
            raise TUIClientError(
                "TUI_NO_COMPATIBLE_AGENT",
                "No tool-free, Session-disabled, workspace-free Agent is available",
            )
        selected = self._select_agent(agents, agent_id)
        cases = [
            item
            for item in self._client.list_evaluation_cases()
            if item.get("agent_definition_id") == selected.get("agent_id")
        ]
        selected_case = self._select_case(cases, evaluation_case_id)
        request = self._read_multiline_request()
        selected_model = model
        if selected_model is None:
            selected_model = self._terminal.read("Model (blank = server default): ").strip() or None

        flow = GovernedTUIFlow(self._client)
        outcome = flow.execute(
            agent_id=str(selected["agent_id"]),
            request=request,
            model=selected_model,
            evaluation_case_id=str(selected_case["case_id"]),
            confirmation_provider=self._prompt_confirmation,
            on_preflight=self._render_preflight,
            on_event=self._render_event,
        )
        self._render_outcome(outcome)
        return outcome

    def _select_agent(
        self,
        agents: list[dict[str, Any]],
        requested_agent_id: str | None,
    ) -> dict[str, Any]:
        if requested_agent_id:
            for item in agents:
                if item.get("agent_id") == requested_agent_id:
                    return item
            raise TUIClientError(
                "TUI_AGENT_NOT_SUPPORTED",
                "Requested Agent is not available in STEP056 TUI Foundation",
            )
        self._terminal.write("\nAvailable tool-free Agents")
        for index, item in enumerate(agents, start=1):
            self._terminal.write(
                f"  {index:>2}. {item.get('name')} [{item.get('agent_id')}] · {item.get('output_contract')}"
            )
        return agents[self._read_index("Agent number: ", len(agents))]

    def _select_case(
        self,
        cases: list[dict[str, Any]],
        requested_case_id: str | None,
    ) -> dict[str, Any]:
        if requested_case_id:
            for item in cases:
                if item.get("case_id") == requested_case_id:
                    return item
            raise TUIClientError(
                "TUI_EVALUATION_CASE_NOT_FOUND",
                "Requested Evaluation case is not compatible with the selected Agent",
            )
        if not cases:
            raise TUIClientError(
                "TUI_EVALUATION_CASE_NOT_FOUND",
                "Selected Agent has no recorded Evaluation case",
            )
        self._terminal.write("\nCompatible recorded Evaluations")
        for index, item in enumerate(cases, start=1):
            self._terminal.write(
                f"  {index:>2}. {item.get('case_id')}@{item.get('version')}"
            )
        return cases[self._read_index("Evaluation number: ", len(cases))]

    def _read_index(self, prompt: str, count: int) -> int:
        while True:
            raw = self._terminal.read(prompt).strip()
            try:
                value = int(raw)
            except ValueError:
                self._terminal.write("Enter a numeric menu index.")
                continue
            if 1 <= value <= count:
                return value - 1
            self._terminal.write(f"Enter a value from 1 to {count}.")

    def _read_multiline_request(self) -> str:
        self._terminal.write("\nRequest input · finish with a single '.' line")
        lines: list[str] = []
        while True:
            line = self._terminal.read("> ")
            if line == ".":
                break
            lines.append(line)
        request = "\n".join(lines).strip()
        if not request:
            raise TUIClientError("TUI_REQUEST_INVALID", "A non-empty request is required")
        return request

    def _prompt_confirmation(self, challenge: str) -> str:
        self._terminal.write("\nExact confirmation challenge")
        self._terminal.write(f"  {challenge}")
        return self._terminal.read("Type exactly: ")

    def _render_header(self) -> None:
        self._terminal.write("=" * 72)
        self._terminal.write(" OKCanvas Agent Runtime · Governed TUI Client Foundation")
        self._terminal.write(" Existing Control API + persisted SSE only · no direct Runtime access")
        self._terminal.write("=" * 72)

    def _render_preflight(self, preflight: dict[str, Any]) -> None:
        self._terminal.write("\n[Preflight]")
        self._terminal.write(f"  Submission      {preflight.get('submission_id')}")
        self._terminal.write(f"  Agent           {preflight.get('agent_definition_id')}@{preflight.get('agent_definition_version')}")
        self._terminal.write(f"  Runtime binding {preflight.get('runtime_binding_sha256')}")
        self._terminal.write(f"  Execution       {preflight.get('execution_mode')}")
        self._terminal.write(f"  Approval        {preflight.get('approval_required')}")

    def _render_event(self, event: dict[str, Any]) -> None:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        detail = next(
            (
                payload.get(key)
                for key in ("status", "code", "agent_id", "tool_name", "output_contract")
                if payload.get(key) is not None
            ),
            None,
        )
        suffix = f" · {detail}" if detail is not None else ""
        self._terminal.write(
            f"  #{int(event.get('sequence') or 0):02d} {event.get('event_type')}{suffix}"
        )

    def _render_outcome(self, outcome: TUIRunOutcome) -> None:
        self._terminal.write("\n[Run]")
        self._terminal.write(
            f"  {outcome.run.get('run_id')} · {outcome.run.get('status')} · "
            f"{outcome.run.get('total_tokens')} tokens"
        )
        self._terminal.write(f"  Invocations     {len(outcome.invocations)}")
        self._terminal.write("\n[Artifact VERIFIED]")
        self._terminal.write(f"  SHA-256         {outcome.artifact.get('sha256')}")
        self._terminal.write(
            json.dumps(outcome.artifact.get("content"), ensure_ascii=False, indent=2, sort_keys=True)
        )
        self._terminal.write("\n[Evaluation]")
        self._terminal.write(
            f"  {outcome.evaluation.get('case_id')} · {outcome.evaluation.get('state')}"
        )
        checks = outcome.evaluation.get("checks")
        if isinstance(checks, dict):
            for key, value in checks.items():
                self._terminal.write(f"  {'PASS' if value else 'FAIL'}  {key}")


def run_tui_from_environment(
    *,
    base_url: str | None = None,
    agent_id: str | None = None,
    model: str | None = None,
    evaluation_case_id: str | None = None,
    terminal: Terminal | None = None,
) -> int:
    active_terminal = terminal or ConsoleTerminal()
    admin_key = os.getenv("OKCANVAS_CONTROL_ADMIN_KEY", "").strip()
    submitter_key = os.getenv("OKCANVAS_RUN_SUBMITTER_KEY", "").strip()
    if len(admin_key) < 16:
        admin_key = active_terminal.read_secret("Local admin key: ").strip()
    if len(submitter_key) < 16:
        submitter_key = active_terminal.read_secret("Run-submitter key: ").strip()
    host = os.getenv("OKCANVAS_API_HOST", "127.0.0.1").strip() or "127.0.0.1"
    if host in {"0.0.0.0", "::"}:
        host = "127.0.0.1"
    port = os.getenv("OKCANVAS_API_PORT", "8765").strip() or "8765"
    host_for_url = f"[{host}]" if ":" in host else host
    config = TUIClientConfig(
        base_url=base_url
        or os.getenv("OKCANVAS_CONTROL_BASE_URL")
        or f"http://{host_for_url}:{port}",
        admin_key=admin_key,
        submitter_key=submitter_key,
    )
    with LocalTUIControlClient(config) as client:
        TUIApplication(client, active_terminal).run_interactive(
            agent_id=agent_id,
            model=model,
            evaluation_case_id=evaluation_case_id,
        )
    return 0
