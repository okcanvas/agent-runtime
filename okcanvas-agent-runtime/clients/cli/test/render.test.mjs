import assert from "node:assert/strict";
import test from "node:test";
import {
  capabilitySummary,
  isFoundationCompatible,
  renderAnswer,
  renderDebugPreflight,
  renderEvaluation,
  renderEventLine,
  renderProgressEvent,
  renderInvocations
} from "../dist/render.js";

const agent = {
  agent_id: "coding-agent",
  version: "1.0.0",
  name: "Coding Agent",
  output_contract: "CodingAgentResult",
  tools: [],
  tool_capabilities: [],
  mcp_servers: [],
  handoffs: [],
  agent_tools: [],
  orchestration_children: [],
  guardrails: [],
  workspace_access: "none",
  session_mode: "disabled"
};

test("foundation capability boundary is explicit", () => {
  assert.equal(isFoundationCompatible(agent), true);
  assert.match(capabilitySummary(agent).join("\n"), /서버 대화 기억 없음/u);
});

test("structured CodingAgentResult renders as friendly text", () => {
  const text = renderAnswer({
    status: "PASS",
    summary: "완료했습니다.",
    findings: [{ title: "확인", detail: "세부 내용", evidence: ["src/router.py:1-4"] }],
    unverified: []
  });
  assert.match(text, /완료했습니다/u);
  assert.match(text, /확인: 세부 내용/u);
  assert.match(text, /src\/router\.py:1-4/u);
  assert.doesNotMatch(text, /"status"/u);
});

test("finding evidence rendering is bounded and removes line breaks", () => {
  const text = renderAnswer({
    status: "PASS",
    summary: "완료",
    findings: [{
      title: "근거",
      detail: "위치",
      evidence: ["src/a.py:1-2\nPRIVATE", "src/b.py:3-4", "src/c.py:5-6", "src/d.py:7-8"]
    }],
    unverified: []
  });
  assert.match(text, /src\/a\.py:1-2 PRIVATE/u);
  assert.match(text, /src\/c\.py:5-6/u);
  assert.doesNotMatch(text, /src\/d\.py/u);
});

test("debug preflight exposes governed diagnostics without changing confirmation flow", () => {
  const text = renderDebugPreflight({
    submission_id: "submission_1",
    runtime_binding_sha256: "binding",
    execution_mode: "IMMEDIATE_AFTER_CONFIRMATION",
    approval_required: false,
    confirmation_challenge: "RUN coding-agent@1.0.0 abc"
  }, agent, undefined);
  assert.match(text, /\[Preflight\]/u);
  assert.match(text, /RUN coding-agent@1\.0\.0 abc/u);
});

test("event and evaluation diagnostics are bounded", () => {
  assert.equal(renderEventLine({ run_id: "run_1", sequence: 1, event_type: "agent.started", payload: { agent_id: "coding-agent" } }), "#01 agent.started · coding-agent");
  assert.match(renderEvaluation(), /NOT RUN/u);
  assert.match(renderEvaluation({ case_id: "case-1", state: "PASSED", checks: { result: true } }), /PASS  result/u);
});

test("session-enabled text-only Agent is CLI compatible", () => {
  const sessionAgent = { ...agent, agent_id: "conversational-coding-agent", session_mode: "sqlite-v1" };
  assert.equal(isFoundationCompatible(sessionAgent), true);
  assert.match(capabilitySummary(sessionAgent).join("\n"), /Runtime Session 대화 기억/u);
});


test("safe read-only Tool and isolated Sub Agent graphs are CLI compatible", () => {
  const toolAgent = {
    ...agent,
    agent_id: "local-text-fingerprint-agent",
    tools: ["local_text_fingerprint"],
    tool_capabilities: [{
      tool_id: "local_text_fingerprint", approval_mode: "NEVER", read_only: true,
      filesystem_access: "none", network_access: "none", shell_access: "none"
    }]
  };
  const approvalAgent = {
    ...toolAgent,
    agent_id: "local-text-metrics-agent",
    tool_capabilities: [{ ...toolAgent.tool_capabilities[0], approval_mode: "ALWAYS" }]
  };
  const handoffAgent = { ...agent, agent_id: "session-handoff-triage-agent", session_mode: "sqlite-v1", handoffs: ["handoff-specialist-agent"] };
  const agentToolAgent = { ...agent, agent_id: "session-agent-tool-manager-agent", session_mode: "sqlite-v1", agent_tools: ["agent-tool-specialist-agent"] };
  assert.equal(isFoundationCompatible(toolAgent), true);
  assert.equal(isFoundationCompatible(approvalAgent), false);
  assert.equal(isFoundationCompatible(handoffAgent), true);
  assert.equal(isFoundationCompatible(agentToolAgent), true);
});

test("normal progress and invocation tree expose Tool and Sub Agent work without raw payloads", () => {
  assert.equal(renderProgressEvent({ run_id: "r", sequence: 1, event_type: "tool.started", payload: { tool_name: "local_text_fingerprint", arguments: "SECRET" } }), "  ↳ Tool local_text_fingerprint 실행");
  assert.equal(renderProgressEvent({ run_id: "r", sequence: 2, event_type: "agent.handoff", payload: { from_agent_id: "triage", to_agent_id: "specialist" } }), "  ↳ Handoff triage → specialist");
  assert.equal(renderProgressEvent({ run_id: "r", sequence: 3, event_type: "agent.tool.completed", payload: { to_agent_id: "specialist", result: "SECRET" } }), "  ✓ Sub Agent specialist 완료");
  const tree = renderInvocations([
    { invocation_kind: "ROOT", agent_definition_id: "manager", state: "SUCCEEDED", depth: 0, ordinal: 0, total_tokens: 30 },
    { invocation_kind: "AGENT_AS_TOOL", agent_definition_id: "specialist", state: "SUCCEEDED", depth: 1, ordinal: 1, total_tokens: 12 }
  ]);
  assert.match(tree, /ROOT · manager/u);
  assert.match(tree, /  AGENT_AS_TOOL · specialist/u);
  assert.doesNotMatch(tree, /SECRET/u);
});

test("bounded project read-only Tool is CLI compatible and clearly labeled", () => {
  const projectAgent = {
    ...agent,
    agent_id: "project-readonly-coding-agent",
    tools: ["project_readonly_inspect"],
    tool_capabilities: [{
      tool_id: "project_readonly_inspect", approval_mode: "NEVER", read_only: true,
      filesystem_access: "read-only", network_access: "none", shell_access: "none"
    }]
  };
  assert.equal(isFoundationCompatible(projectAgent), true);
  const summary = capabilitySummary(projectAgent).join("\n");
  assert.match(summary, /설정된 프로젝트의 텍스트 파일/u);
  assert.match(summary, /파일 쓰기·Shell·Git 명령·인터넷 접근 없음/u);
});

test("bounded orchestration is visible and renders child results", () => {
  const orchestrationAgent = {
    ...agent,
    agent_id: "bounded-orchestration-manager-agent",
    output_contract: "BoundedOrchestrationResult",
    orchestration_children: [
      "bounded-orchestration-architecture-agent",
      "bounded-orchestration-risk-agent"
    ]
  };
  assert.equal(isFoundationCompatible(orchestrationAgent), true);
  assert.match(capabilitySummary(orchestrationAgent).join("\n"), /고정 Specialist 2개/u);
  const answer = renderAnswer({
    schema_version: "okcanvas-bounded-orchestration-result-v1",
    status: "PARTIAL",
    summary: "2/2 specialists completed; aggregate status PARTIAL.",
    child_count: 2,
    children: [
      { ordinal: 1, agent_definition_id: "architecture", result: { status: "PASS", summary: "Architecture complete." } },
      { ordinal: 2, agent_definition_id: "risk", result: { status: "PARTIAL", summary: "Risk remains." } }
    ]
  });
  assert.match(answer, /Specialist 결과/u);
  assert.match(answer, /architecture · PASS · Architecture complete/u);
  assert.equal(
    renderProgressEvent({ run_id: "r", sequence: 1, event_type: "orchestration.child.started", payload: { ordinal: 2, agent_id: "risk" } }),
    "  ↳ Specialist #2 risk 시작"
  );
});
