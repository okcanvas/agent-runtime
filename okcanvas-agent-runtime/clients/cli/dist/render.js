function strings(value) {
    return Array.isArray(value) ? value.map((item) => String(item)) : [];
}
function boundedEvidence(value) {
    if (!Array.isArray(value))
        return [];
    return value
        .slice(0, 3)
        .map((item) => String(item).replace(/[\r\n]+/gu, " ").trim().slice(0, 160))
        .filter(Boolean);
}
function findingLines(value) {
    if (!Array.isArray(value))
        return [];
    return value.map((item) => {
        if (!item || typeof item !== "object" || Array.isArray(item))
            return String(item);
        const finding = item;
        const title = String(finding.title ?? "확인 사항");
        const detail = String(finding.detail ?? "");
        const evidence = boundedEvidence(finding.evidence);
        const body = detail ? `${title}: ${detail}` : title;
        return evidence.length > 0 ? `${body} [${evidence.join(", ")}]` : body;
    });
}
function present(value, fallback = "-") {
    if (value === undefined || value === null || value === "")
        return fallback;
    return String(value);
}
function eventDetail(event) {
    const payload = event.payload ?? {};
    for (const key of ["agent_id", "model", "output_contract", "tool_name", "to_agent_id", "target_agent_id", "session_id"]) {
        const value = payload[key];
        if (value !== undefined && value !== null && value !== "")
            return String(value);
    }
    return "";
}
function isolatedCapabilityCount(agent) {
    return Number(agent.tools.length > 0) + Number(agent.handoffs.length > 0) + Number(agent.agent_tools.length > 0) + Number(agent.orchestration_children.length > 0);
}
function safeReadOnlyTool(agent) {
    if (agent.tools.length !== 1 || agent.tool_capabilities.length !== 1 || agent.session_mode !== "disabled")
        return false;
    const capability = agent.tool_capabilities[0] ?? {};
    const filesystemAccess = capability.filesystem_access;
    const filesystemAllowed = filesystemAccess === "none"
        || (agent.tools[0] === "project_readonly_inspect" && filesystemAccess === "read-only");
    return capability.tool_id === agent.tools[0]
        && capability.approval_mode === "NEVER"
        && capability.read_only === true
        && filesystemAllowed
        && capability.network_access === "none"
        && capability.shell_access === "none";
}
export function shortSessionId(sessionId) {
    return sessionId.startsWith("session_") ? sessionId.slice(8, 16) : sessionId.slice(0, 8);
}
export function isCliCompatible(agent) {
    if (!new Set(["disabled", "sqlite-v1"]).has(agent.session_mode))
        return false;
    if (agent.workspace_access !== "none" || agent.mcp_servers.length > 0 || agent.guardrails.length > 0)
        return false;
    if (isolatedCapabilityCount(agent) > 1)
        return false;
    if (agent.tools.length > 0)
        return safeReadOnlyTool(agent);
    if (agent.handoffs.length > 0) {
        return agent.handoffs.length === 1 && agent.agent_tools.length === 0;
    }
    if (agent.agent_tools.length > 0) {
        return agent.agent_tools.length === 1 && agent.handoffs.length === 0;
    }
    if (agent.orchestration_children.length > 0) {
        return agent.orchestration_children.length === 2;
    }
    return true;
}
export function capabilityKind(agent) {
    if (agent.tools.length === 1)
        return `read-only Tool ${agent.tools[0]}`;
    if (agent.handoffs.length === 1)
        return `Handoff → ${agent.handoffs[0]}`;
    if (agent.agent_tools.length === 1)
        return `Sub Agent → ${agent.agent_tools[0]}`;
    if (agent.orchestration_children.length === 2)
        return `병렬 Specialist 2개 → ${agent.orchestration_children.join(", ")}`;
    return "text-only";
}
export function capabilitySummary(agent) {
    const capabilities = [];
    if (agent.tools.includes("project_readonly_inspect")) {
        capabilities.push("설정된 프로젝트의 텍스트 파일을 제한적으로 읽기 가능");
        capabilities.push("파일 쓰기·Shell·Git 명령·인터넷 접근 없음");
    }
    else {
        capabilities.push("프로젝트 파일·Shell·인터넷 접근 없음");
    }
    if (agent.session_mode === "sqlite-v1")
        capabilities.push("Runtime Session 대화 기억 사용 · 같은 Session의 이전 Turn 참조 가능");
    else
        capabilities.push("서버 대화 기억 없음 · 각 요청은 독립 실행");
    if (agent.tools.length === 1)
        capabilities.push(`승인 없는 read-only Function Tool 사용 가능: ${agent.tools[0]}`);
    else if (agent.handoffs.length === 1)
        capabilities.push(`전문 Agent로 한 번 Handoff 가능: ${agent.handoffs[0]}`);
    else if (agent.agent_tools.length === 1)
        capabilities.push(`전문 Sub Agent를 Tool로 한 번 호출 가능: ${agent.agent_tools[0]}`);
    else if (agent.orchestration_children.length === 2)
        capabilities.push(`고정 Specialist 2개를 병렬 실행하고 선언 순서로 집계: ${agent.orchestration_children.join(", ")}`);
    else
        capabilities.push("현재는 입력한 대화 텍스트만 분석 가능");
    return capabilities;
}
function sessionModeLabel(agent) {
    return agent.session_mode === "sqlite-v1" ? "대화 기억" : "독립 요청";
}
function agentLine(agent) {
    return `${agent.agent_id} · ${agent.name} · ${sessionModeLabel(agent)} · ${capabilityKind(agent)}`;
}
export function renderAgents(agents, activeId) {
    return agents.map((agent) => `${agent.agent_id === activeId ? "*" : " "} ${agentLine(agent)}`).join("\n");
}
export function renderAgentChoices(agents) {
    return agents.map((agent, index) => `  ${index + 1}. ${agentLine(agent)}`).join("\n");
}
export function renderSession(session) {
    return [
        `Session: ${session.session_id}`,
        `State: ${session.state}`,
        `Agent: ${session.agent_definition_id}@${session.agent_definition_version}`,
        `Turns: ${session.turn_count}`,
        `Items: ${session.item_count}`,
        `History Encryption Key ID: ${session.history_encryption_key_id ?? "unavailable"}`,
        `Active Run: ${session.active_run_id ?? "none"}`,
        `Updated: ${session.updated_at}`
    ].join("\n");
}
export function renderSessions(sessions, activeSessionId) {
    if (sessions.length === 0)
        return "현재 Agent의 Session이 없습니다.";
    return sessions.map((session, index) => {
        const active = session.session_id === activeSessionId ? "*" : " ";
        return `${active} ${index + 1}. ${session.session_id} · ${session.state} · turns ${session.turn_count} · items ${session.item_count}`;
    }).join("\n");
}
export function renderAnswer(content) {
    const summary = typeof content.summary === "string" ? content.summary.trim() : "";
    const findings = findingLines(content.findings);
    const unverified = strings(content.unverified);
    const children = Array.isArray(content.children) ? content.children : [];
    const lines = ["", "Agent", "─────"];
    if (summary)
        lines.push(summary);
    if (findings.length > 0) {
        lines.push("", "확인 사항");
        findings.forEach((item, index) => lines.push(`${index + 1}. ${item}`));
    }
    if (unverified.length > 0) {
        lines.push("", "확인되지 않은 사항");
        unverified.forEach((item) => lines.push(`- ${item}`));
    }
    if (children.length > 0) {
        lines.push("", "Specialist 결과");
        children.forEach((item, index) => {
            if (!item || typeof item !== "object" || Array.isArray(item))
                return;
            const child = item;
            const result = child.result && typeof child.result === "object" && !Array.isArray(child.result)
                ? child.result
                : {};
            lines.push(`${index + 1}. ${present(child.agent_definition_id)} · ${present(result.status)} · ${present(result.summary)}`);
        });
    }
    if (!summary && findings.length === 0 && unverified.length === 0 && children.length === 0) {
        lines.push(JSON.stringify(content, null, 2));
    }
    return lines.join("\n");
}
export function answerSummary(content) {
    return typeof content.summary === "string" && content.summary.trim()
        ? content.summary.trim()
        : JSON.stringify(content);
}
function invocationDepth(item) {
    const value = Number(item.depth ?? 0);
    return Number.isFinite(value) && value >= 0 ? value : 0;
}
export function renderInvocations(invocations) {
    if (invocations.length === 0)
        return "Invocation이 없습니다.";
    const sorted = [...invocations].sort((left, right) => {
        const ordinalDiff = Number(left.ordinal ?? 0) - Number(right.ordinal ?? 0);
        return ordinalDiff || invocationDepth(left) - invocationDepth(right);
    });
    return sorted.map((item) => {
        const indent = "  ".repeat(invocationDepth(item));
        return `${indent}${present(item.invocation_kind)} · ${present(item.agent_definition_id)} · ${present(item.state)} · ${present(item.total_tokens, "0")} tokens`;
    }).join("\n");
}
export function renderDetails(outcome) {
    return [
        `Run: ${outcome.run.run_id}`,
        `Status: ${outcome.run.status}`,
        `Tokens: ${outcome.run.total_tokens}`,
        `Agent: ${outcome.agent.agent_id}@${outcome.agent.version}`,
        `Capability: ${capabilityKind(outcome.agent)}`,
        `Session: ${present(outcome.preflight.session_id, "disabled")}`,
        `Invocations: ${outcome.invocations.length}`,
        renderInvocations(outcome.invocations),
        `Artifact: ${outcome.artifact.artifact_id}`,
        `Artifact SHA-256: ${outcome.artifact.sha256}`,
        `Evaluation: ${outcome.evaluation ? String(outcome.evaluation.state ?? "UNKNOWN") : "not requested"}`
    ].join("\n");
}
export function renderEventLine(event) {
    const detail = eventDetail(event);
    return `#${String(event.sequence).padStart(2, "0")} ${event.event_type}${detail ? ` · ${detail}` : ""}`;
}
export function renderProgressEvent(event) {
    const payload = event.payload ?? {};
    if (event.event_type === "tool.started")
        return `  ↳ Tool ${present(payload.tool_name)} 실행`;
    if (event.event_type === "tool.completed")
        return `  ✓ Tool ${present(payload.tool_name)} 완료`;
    if (event.event_type === "agent.handoff")
        return `  ↳ Handoff ${present(payload.from_agent_id)} → ${present(payload.to_agent_id)}`;
    if (event.event_type === "agent.tool.started")
        return `  ↳ Sub Agent ${present(payload.to_agent_id)} 호출`;
    if (event.event_type === "agent.tool.completed")
        return `  ✓ Sub Agent ${present(payload.to_agent_id)} 완료`;
    if (event.event_type === "orchestration.child.started")
        return `  ↳ Specialist #${present(payload.ordinal)} ${present(payload.agent_id)} 시작`;
    if (event.event_type === "orchestration.child.completed")
        return `  ✓ Specialist #${present(payload.ordinal)} ${present(payload.agent_id)} 완료`;
    if (event.event_type === "orchestration.child.failed")
        return `  ✗ Specialist #${present(payload.ordinal)} ${present(payload.agent_id)} 실패`;
    if (event.event_type === "orchestration.child.cancelled")
        return `  - Specialist #${present(payload.ordinal)} ${present(payload.agent_id)} 취소`;
    return undefined;
}
export function renderEvents(events) {
    return events.map(renderEventLine).join("\n");
}
export function renderDebugPreflight(preflight, agent, model) {
    return [
        "",
        "[Preflight]",
        `  Submission      ${present(preflight.submission_id)}`,
        `  Agent           ${agent.agent_id}@${agent.version}`,
        `  Capability      ${capabilityKind(agent)}`,
        `  Session         ${present(preflight.session_id, "disabled")}`,
        `  Runtime binding ${present(preflight.runtime_binding_sha256)}`,
        `  Execution       ${present(preflight.execution_mode)}`,
        `  Approval        ${present(preflight.approval_required)}`,
        `  Model           ${model ?? present(preflight.model, "server default")}`,
        "",
        "[Debug] Exact confirmation challenge received",
        `  ${present(preflight.confirmation_challenge)}`
    ].join("\n");
}
export function renderDebugRun(outcome) {
    return [
        "",
        "[Run]",
        `  ${outcome.run.run_id} · ${outcome.run.status} · ${outcome.run.total_tokens} tokens`,
        `  Session         ${present(outcome.preflight.session_id, "disabled")}`,
        `  Invocations     ${outcome.invocations.length}`,
        renderInvocations(outcome.invocations)
    ].join("\n");
}
export function renderDebugArtifact(artifact) {
    return [
        "",
        `[Artifact ${artifact.verified_at ? "VERIFIED" : "UNVERIFIED"}]`,
        `  ID              ${artifact.artifact_id}`,
        `  SHA-256         ${artifact.sha256}`,
        JSON.stringify(artifact.content, null, 2)
    ].join("\n");
}
export function renderEvaluation(evaluation) {
    if (!evaluation)
        return "\n[Evaluation]\n  NOT RUN";
    const checks = evaluation.checks;
    const lines = [
        "",
        "[Evaluation]",
        `  ${present(evaluation.case_id)} · ${present(evaluation.state, "UNKNOWN")}`
    ];
    if (checks && typeof checks === "object" && !Array.isArray(checks)) {
        for (const [name, value] of Object.entries(checks)) {
            lines.push(`  ${value === true ? "PASS" : "FAIL"}  ${name}`);
        }
    }
    return lines.join("\n");
}
// Historical STEP056B/C test compatibility. Product code uses isCliCompatible.
export const isFoundationCompatible = isCliCompatible;
//# sourceMappingURL=render.js.map