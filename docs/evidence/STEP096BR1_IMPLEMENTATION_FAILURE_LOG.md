# STEP096BR1 Implementation / Live-Harness Failure Log

STEP: STEP096BR1_FOCUSED_WINDOWS_LIVE_GROUNDED_STRUCTURED_DELEGATION_ACCEPTANCE
Runtime Product: STEP096B_GROUNDED_LLM_STRUCTURED_DELEGATION_ADMISSION_FOUNDATION / 2.80.0
Mode: Workspace acceptance-harness only; Runtime Product behavior unchanged.

## 1. Live cannot be claimed from the analysis container

The extracted R12 package contains no `.env.local` / `.env.local.cmd`, and the analysis process has no
configured `OPENAI_API_KEY` or `OKCANVAS_AGENT_MODEL`. A direct harness dry-run therefore failed closed at
preflight. This is expected and is not converted to PASS.

Recurrence rule: only the Windows entrypoint may load the local environment and set the explicit BR1 Live
gate. No package may embed local environment files or credentials.

## 2. Eight semantic scenarios require ten actual Runtime turns

`김민수 연락처 알려줘` intentionally produces same-name ambiguity. Cross-domain `그 사람 ...` assertions
must not depend on that ambiguous Session. BR1 therefore gives each scenario its own Session. The two
focus-dependent scenarios each execute an additional fixture turn (`플랫폼팀 김민수 선임 연락처 알려줘`)
that must first produce normalized stable `employee-0017` evidence.

Recurrence rule: scenario isolation is mandatory; no acceptance case may inherit focus or ambiguity from a
previous unrelated case.

## 3. Hint MCP traffic must not be mistaken for execution-specialist traffic

STEP096A/096B intentionally performs two Organization Context hint searches before the Root LLM turn:
`search_organization_context` and `search_organization_terms`. Therefore “no specialist invoked” cannot mean
“no Organization Connector traffic”. BR1 snapshots fake-system requests per Turn and distinguishes the two
hint API paths from execution paths such as `/api/v1/context/resolve` and Groupware resource APIs.

Recurrence rule: direct-answer/no-specialist cases require zero `agent.tool.requested`, zero admitted child,
zero child `tool.started`, and zero execution API traffic while still requiring exact raw-utterance hint
searches.

## 4. Stable ID and Tool-name authority remain Runtime-owned

The Live harness never accepts model-produced stable IDs as evidence. Organization resolve execution must
use a natural-language surface (for example `김민수` or `한빛`), while Session-focus Groupware execution must
forward the server-owned `employee-0017` through exact `context_ref` evidence after admission.

Recurrence rule: BR1 must observe `agent.tool.requested -> agent.tool.admitted -> agent.tool.started ->
child MCP tool.started -> agent.tool.output.normalized` for delegated reads. `selected_child_mcp_connected`
must be true only on the admitted child event.

## 5. Current Runtime README had stale successor narrative

R12 current-document markers were STEP096B but `okcanvas-agent-runtime/README.md` body still called STEP096A
the current candidate and STEP096B the next step. This is tracked as WORKSPACE-ISSUE-071 and corrected in
R12R1.

## 6. BR1 Live evidence mutable registration was missing during initial harness construction

Before any R12R1 immutable manifest/package was generated, the new BR1 Live output path was found absent
from `MUTABLE_ACCEPTANCE_EVIDENCE`. This would have repeated the provenance class recorded by
WORKSPACE-ISSUE-057 if packaging had proceeded.

Correction: register the exact BR1 evidence path as mutable and make R12R1 static validation fail when the
registration is absent. Tracked as WORKSPACE-ISSUE-072.
