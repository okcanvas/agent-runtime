import { readFileSync } from "node:fs";
import { createInterface } from "node:readline/promises";
import { ControlApiClient } from "./api-client.js";
import { CliError, type RuntimeConfig } from "./config.js";
import {
  answerSummary,
  capabilitySummary,
  isCliCompatible,
  renderAgentChoices,
  renderAgents,
  renderAnswer,
  renderDebugArtifact,
  renderDebugPreflight,
  renderDebugRun,
  renderDetails,
  renderEvaluation,
  renderEventLine,
  renderEvents,
  renderInvocations,
  renderProgressEvent,
  renderSession,
  renderSessions,
  shortSessionId
} from "./render.js";
import type {
  AgentDefinition,
  CliOptions,
  ConversationEntry,
  ExecutionObserver,
  JsonObject,
  ProductSession,
  RunOutcome
} from "./types.js";

const CANONICAL_CONVERSATIONAL_AGENT_ID = "conversational-coding-agent";

const HELP = `명령
  /help                    도움말
  /agents                  사용 가능한 Agent
  /use <agent-id>          Agent 전환 · Session Agent는 새 Session 생성
  /capabilities            현재 Agent가 할 수 있는 일
  /model <id|default>      모델 변경
  /paste                   여러 줄 입력 · 단독 . 으로 종료
  /status                  Runtime·Agent·Model·debug·Session 상태
  /debug [on|off]          개발 진단 모드 조회/전환
  /new                     현재 Agent의 새 Runtime Session 시작
  /session                 현재 Runtime Session 정보
  /sessions                현재 Agent의 Runtime Session 목록
  /resume <id|number>      기존 ACTIVE Session 재개
  /clear                   현재 Session 기록 삭제 후 새 Session 생성
  /history                 이 CLI 프로세스에서 표시된 대화
  /details                 마지막 Run 상세
  /events                  마지막 Run Event
  /invocations             마지막 Root/Sub Agent 실행 구조
  /json                    마지막 Artifact 원본 JSON
  /evaluate <case-id>      마지막 Run을 지정 Evaluation case로 평가
  /quit                    종료`;

interface LineSource {
  next(prompt: string): Promise<string | null>;
  close(): void;
}

class InteractiveLineSource implements LineSource {
  private readonly rl = createInterface({ input: process.stdin, output: process.stdout });
  async next(prompt: string): Promise<string | null> {
    try {
      return await this.rl.question(prompt);
    } catch {
      return null;
    }
  }
  close(): void { this.rl.close(); }
}

class ScriptLineSource implements LineSource {
  private index = 0;
  private readonly lines: string[];
  constructor(path: string) {
    this.lines = readFileSync(path, "utf8").split(/\r?\n/u).filter((line) => line.length > 0);
  }
  async next(prompt: string): Promise<string | null> {
    const value = this.lines[this.index++];
    if (value === undefined) return null;
    process.stdout.write(`${prompt}${value}\n`);
    return value;
  }
  close(): void {}
}

export class PersistentAgentCli {
  private readonly client: ControlApiClient;
  private readonly config: RuntimeConfig;
  private readonly options: CliOptions;
  private readonly input: LineSource;
  private agents: AgentDefinition[] = [];
  private activeAgent!: AgentDefinition;
  private activeSession: ProductSession | undefined;
  private model: string | undefined;
  private lastOutcome: RunOutcome | undefined;
  private requestCount = 0;
  private debugEnabled: boolean;
  private runtimeHealth: JsonObject = {};
  private readonly localConversation: ConversationEntry[] = [];

  constructor(config: RuntimeConfig, options: CliOptions) {
    this.client = new ControlApiClient(config);
    this.config = config;
    this.options = options;
    this.model = config.model;
    this.debugEnabled = options.debug;
    this.input = options.scriptFile ? new ScriptLineSource(options.scriptFile) : new InteractiveLineSource();
  }

  async run(): Promise<number> {
    try {
      this.runtimeHealth = await this.client.health();
      this.agents = (await this.client.listAgents()).filter(isCliCompatible);
      if (this.agents.length === 0) throw new CliError("CLI_NO_COMPATIBLE_AGENT", "실행 가능한 text-only Agent가 없습니다");
      this.activeAgent = await this.selectInitialAgent(this.config.defaultAgentId);
      await this.activateSession(this.options.sessionId);
      this.printBanner(String(this.runtimeHealth.version ?? "unknown"));
      while (true) {
        const raw = await this.input.next(this.prompt());
        if (raw === null) break;
        const line = raw.trim();
        if (!line) continue;
        if (line.startsWith("/")) {
          if (await this.handleCommand(line)) break;
          continue;
        }
        await this.executeRequest(line);
      }
      console.log(`\n종료 · 이 프로세스에서 ${this.requestCount}개 요청을 실행했습니다.`);
      return 0;
    } finally {
      this.input.close();
    }
  }

  private sessionEnabled(agent = this.activeAgent): boolean {
    return agent.session_mode === "sqlite-v1";
  }

  private prompt(): string {
    const session = this.activeSession ? ` [${shortSessionId(this.activeSession.session_id)}]` : "";
    return `\n${this.activeAgent.agent_id}${session}> `;
  }

  private async selectInitialAgent(requested?: string): Promise<AgentDefinition> {
    if (requested) {
      const found = this.agents.find((item) => item.agent_id === requested);
      if (!found) throw new CliError("CLI_AGENT_NOT_FOUND", `사용 가능한 Agent가 아닙니다: ${requested}`);
      return found;
    }
    const canonical = this.agents.find((item) => item.agent_id === CANONICAL_CONVERSATIONAL_AGENT_ID);
    if (canonical) {
      console.log(`기본 대화 Agent: ${canonical.agent_id}`);
      return canonical;
    }
    if (this.agents.length === 1) return this.agents[0]!;
    if (this.options.scriptFile) {
      throw new CliError("CLI_AGENT_REQUIRED", "Script mode with multiple Agents requires --agent-id");
    }
    console.log("사용할 Agent를 선택하세요.");
    console.log(renderAgentChoices(this.agents));
    while (true) {
      const answer = await this.input.next("Agent 번호 또는 ID: ");
      if (answer === null) throw new CliError("CLI_AGENT_SELECTION_CANCELLED", "Agent selection was cancelled");
      const value = answer.trim();
      const numeric = Number.parseInt(value, 10);
      if (/^\d+$/u.test(value) && numeric >= 1 && numeric <= this.agents.length) {
        return this.agents[numeric - 1]!;
      }
      const found = this.agents.find((item) => item.agent_id === value);
      if (found) return found;
      console.log("번호 또는 정확한 Agent ID를 입력하세요.");
    }
  }

  private async activateSession(requestedSessionId?: string): Promise<void> {
    this.activeSession = undefined;
    if (!this.sessionEnabled()) {
      if (requestedSessionId) {
        throw new CliError("CLI_SESSION_AGENT_MISMATCH", "--session-id requires a Session-enabled Agent");
      }
      return;
    }
    if (requestedSessionId) {
      this.activeSession = await this.validateSessionForActiveAgent(
        await this.client.getSession(requestedSessionId)
      );
      console.log(`Runtime Session 재개: ${this.activeSession.session_id} · turns ${this.activeSession.turn_count}`);
      return;
    }
    this.activeSession = await this.client.createSession(this.activeAgent.agent_id);
    console.log(`새 Runtime Session: ${this.activeSession.session_id}`);
  }

  private async validateSessionForActiveAgent(session: ProductSession): Promise<ProductSession> {
    if (session.state !== "ACTIVE") {
      throw new CliError("CLI_SESSION_NOT_ACTIVE", `Session is not ACTIVE: ${session.session_id}`);
    }
    if (session.agent_definition_id !== this.activeAgent.agent_id) {
      throw new CliError(
        "CLI_SESSION_AGENT_MISMATCH",
        `Session ${session.session_id} belongs to ${session.agent_definition_id}, not ${this.activeAgent.agent_id}`
      );
    }
    return session;
  }

  private printBanner(version: string): void {
    console.log("============================================================");
    console.log(" OKCanvas Agent CLI · Node.js/TypeScript persistent client");
    console.log("============================================================");
    const session = this.activeSession ? ` · Session ${shortSessionId(this.activeSession.session_id)}` : "";
    console.log(`Runtime ${version} · Agent ${this.activeAgent.agent_id}${session} · Debug ${this.debugEnabled ? "ON" : "OFF"}`);
    capabilitySummary(this.activeAgent).forEach((line) => console.log(`- ${line}`));
    const continuity = this.activeSession ? "같은 Session에서 계속 질문할 수 있습니다." : "종료할 때까지 계속 질문할 수 있습니다.";
    console.log(`/help 명령으로 사용법을 확인하세요. ${continuity}`);
  }

  private async handleCommand(line: string): Promise<boolean> {
    const [command, ...rest] = line.split(/\s+/u);
    const argument = rest.join(" ").trim();
    switch (command) {
      case "/quit":
      case "/exit":
        return true;
      case "/help":
        console.log(HELP);
        return false;
      case "/agents":
        console.log(renderAgents(this.agents, this.activeAgent.agent_id));
        return false;
      case "/use":
        await this.changeAgent(argument);
        return false;
      case "/capabilities":
        capabilitySummary(this.activeAgent).forEach((item) => console.log(`- ${item}`));
        return false;
      case "/model":
        if (!argument) console.log(`현재 모델: ${this.model ?? "server default"}`);
        else {
          this.model = argument === "default" ? undefined : argument;
          console.log(`모델: ${this.model ?? "server default"}`);
        }
        return false;
      case "/status":
        this.printStatus();
        return false;
      case "/debug":
        this.handleDebugCommand(argument);
        return false;
      case "/new":
        await this.createNewSession();
        return false;
      case "/session":
        await this.showCurrentSession();
        return false;
      case "/sessions":
        await this.showSessions();
        return false;
      case "/resume":
        await this.resumeSession(argument);
        return false;
      case "/clear":
        await this.clearCurrentSession();
        return false;
      case "/history":
        this.showLocalHistory();
        return false;
      case "/details":
        console.log(this.lastOutcome ? renderDetails(this.lastOutcome) : "아직 실행한 Run이 없습니다.");
        return false;
      case "/events":
        console.log(this.lastOutcome ? renderEvents(this.lastOutcome.events) : "아직 실행한 Run이 없습니다.");
        return false;
      case "/invocations":
        console.log(this.lastOutcome ? renderInvocations(this.lastOutcome.invocations) : "아직 실행한 Run이 없습니다.");
        return false;
      case "/json":
        console.log(this.lastOutcome ? JSON.stringify(this.lastOutcome.artifact.content, null, 2) : "아직 실행한 Run이 없습니다.");
        return false;
      case "/evaluate":
        await this.evaluateLastRun(argument);
        return false;
      case "/paste": {
        const lines: string[] = [];
        console.log("여러 줄 입력 · 단독 . 으로 종료");
        while (true) {
          const value = await this.input.next("| ");
          if (value === null || value === ".") break;
          lines.push(value);
        }
        const request = lines.join("\n").trim();
        if (request) await this.executeRequest(request);
        return false;
      }
      default:
        console.log(`알 수 없는 명령입니다: ${command} · /help를 사용하세요.`);
        return false;
    }
  }

  private async changeAgent(agentId: string): Promise<void> {
    if (!agentId) {
      console.log("사용법: /use <agent-id>");
      return;
    }
    const found = this.agents.find((item) => item.agent_id === agentId);
    if (!found) {
      console.log(`사용 가능한 Agent가 아닙니다: ${agentId}`);
      return;
    }
    this.activeAgent = found;
    this.lastOutcome = undefined;
    this.localConversation.length = 0;
    await this.activateSession();
    console.log(`Agent를 ${found.agent_id}로 변경했습니다.`);
    capabilitySummary(found).forEach((item) => console.log(`- ${item}`));
  }

  private async createNewSession(): Promise<void> {
    if (!this.sessionEnabled()) {
      console.log("현재 Agent는 Runtime Session을 지원하지 않습니다.");
      return;
    }
    this.activeSession = await this.client.createSession(this.activeAgent.agent_id);
    this.lastOutcome = undefined;
    this.localConversation.length = 0;
    console.log(`새 Runtime Session을 시작했습니다: ${this.activeSession.session_id}`);
  }

  private async showCurrentSession(): Promise<void> {
    if (!this.activeSession) {
      console.log("현재 Agent에는 Runtime Session이 없습니다.");
      return;
    }
    this.activeSession = await this.client.getSession(this.activeSession.session_id);
    console.log(renderSession(this.activeSession));
  }

  private async sessionsForActiveAgent(): Promise<ProductSession[]> {
    if (!this.sessionEnabled()) return [];
    return (await this.client.listSessions()).filter(
      (session) => session.agent_definition_id === this.activeAgent.agent_id
    );
  }

  private async showSessions(): Promise<void> {
    if (!this.sessionEnabled()) {
      console.log("현재 Agent는 Runtime Session을 지원하지 않습니다.");
      return;
    }
    const sessions = await this.sessionsForActiveAgent();
    console.log(renderSessions(sessions, this.activeSession?.session_id));
  }

  private async resumeSession(argument: string): Promise<void> {
    if (!this.sessionEnabled()) {
      console.log("현재 Agent는 Runtime Session을 지원하지 않습니다.");
      return;
    }
    if (!argument) {
      console.log("사용법: /resume <session-id|number>");
      await this.showSessions();
      return;
    }
    const sessions = await this.sessionsForActiveAgent();
    let selected: ProductSession | undefined;
    if (/^\d+$/u.test(argument)) {
      const index = Number.parseInt(argument, 10) - 1;
      selected = sessions[index];
    } else {
      selected = sessions.find((session) => session.session_id === argument);
      if (!selected) {
        try {
          selected = await this.client.getSession(argument);
        } catch {
          // Use the friendly bounded error below.
        }
      }
    }
    if (!selected) {
      console.log(`Session을 찾을 수 없습니다: ${argument}`);
      return;
    }
    this.activeSession = await this.validateSessionForActiveAgent(selected);
    this.lastOutcome = undefined;
    this.localConversation.length = 0;
    console.log(`Runtime Session을 재개했습니다: ${this.activeSession.session_id} · turns ${this.activeSession.turn_count}`);
  }

  private async clearCurrentSession(): Promise<void> {
    if (!this.activeSession) {
      console.log("지울 Runtime Session이 없습니다.");
      return;
    }
    let confirmed = this.options.assumeYes;
    if (!confirmed) {
      const answer = await this.input.next(`Session ${shortSessionId(this.activeSession.session_id)} 기록을 지울까요? [y/N] `);
      confirmed = answer !== null && new Set(["y", "yes"]).has(answer.trim().toLowerCase());
    }
    if (!confirmed) {
      console.log("Session clear를 취소했습니다.");
      return;
    }
    const cleared = await this.client.clearSession(this.activeSession.session_id);
    console.log(`Session을 지웠습니다: ${cleared.session_id}`);
    this.activeSession = await this.client.createSession(this.activeAgent.agent_id);
    this.lastOutcome = undefined;
    this.localConversation.length = 0;
    console.log(`새 Runtime Session을 시작했습니다: ${this.activeSession.session_id}`);
  }

  private showLocalHistory(): void {
    if (this.localConversation.length === 0) {
      console.log("이 CLI 프로세스에서 표시된 대화가 없습니다. 재개한 과거 Session 원문은 서버에서 자동 노출하지 않습니다.");
      return;
    }
    console.log("이 CLI 프로세스의 대화");
    console.log("────────────────────");
    for (const entry of this.localConversation) {
      console.log(`${entry.role === "user" ? "You" : "Agent"}: ${entry.text}`);
    }
  }

  private printStatus(): void {
    console.log([
      `Runtime: ${String(this.runtimeHealth.version ?? "unknown")}`,
      `Control API: ${this.config.baseUrl}`,
      `Agent: ${this.activeAgent.agent_id}@${this.activeAgent.version}`,
      `Model: ${this.model ?? "server default"}`,
      `Debug: ${this.debugEnabled ? "ON" : "OFF"}`,
      `Session: ${this.activeSession?.session_id ?? "disabled"}`,
      `Session Turns: ${this.activeSession?.turn_count ?? 0}`,
      `Session Items: ${this.activeSession?.item_count ?? 0}`,
      `Evaluation default: ${this.options.evaluationCaseId ?? "off"}`,
      `Last Run: ${this.lastOutcome?.run.run_id ?? "none"}`
    ].join("\n"));
  }

  private handleDebugCommand(argument: string): void {
    if (!argument) {
      console.log(`Debug mode: ${this.debugEnabled ? "ON" : "OFF"}`);
      return;
    }
    const normalized = argument.toLowerCase();
    if (normalized !== "on" && normalized !== "off") {
      console.log("사용법: /debug on 또는 /debug off");
      return;
    }
    this.debugEnabled = normalized === "on";
    console.log(`Debug mode: ${this.debugEnabled ? "ON" : "OFF"}`);
  }

  private async evaluateLastRun(caseId: string): Promise<void> {
    if (!this.lastOutcome) {
      console.log("평가할 마지막 Run이 없습니다.");
      return;
    }
    if (!caseId) {
      console.log("사용법: /evaluate <case-id>");
      return;
    }
    console.log(`Evaluation 실행 중: ${caseId}`);
    const evaluation = await this.client.evaluate(this.lastOutcome.run.run_id, caseId);
    this.lastOutcome = { ...this.lastOutcome, evaluation };
    console.log(renderEvaluation(evaluation));
  }

  private executionObserver(): ExecutionObserver {
    let progressStarted = false;
    return {
      onPreflight: (preflight, agent, model) => {
        if (this.debugEnabled) console.log(renderDebugPreflight(preflight, agent, model));
      },
      onConfirmed: () => {
        if (this.debugEnabled) console.log("\n[Events]");
      },
      onEvent: (event) => {
        if (this.debugEnabled) {
          console.log(`  ${renderEventLine(event)}`);
          return;
        }
        const progress = renderProgressEvent(event);
        if (!progress) return;
        if (!progressStarted) {
          progressStarted = true;
          console.log("\n[진행]");
        }
        console.log(progress);
      }
    };
  }

  private async executeRequest(requestText: string): Promise<void> {
    if (this.sessionEnabled() && !this.activeSession) {
      throw new CliError("CLI_SESSION_REQUIRED", "Session-enabled Agent has no active Runtime Session");
    }
    console.log("실행 준비 중...");
    const outcome = await this.client.execute(
      this.activeAgent,
      requestText,
      this.model,
      this.activeSession?.session_id,
      async () => {
        if (this.options.assumeYes) return true;
        const answer = await this.input.next(`Run with ${this.activeAgent.agent_id}? [Y/n] `);
        return answer !== null && (answer.trim() === "" || answer.trim().toLowerCase() === "y" || answer.trim().toLowerCase() === "yes");
      },
      this.options.evaluationCaseId,
      this.executionObserver()
    );
    if (!outcome) {
      console.log("실행하지 않았습니다. 미확정 preflight는 Runtime 보존 정책에 따라 관리됩니다.");
      return;
    }
    this.lastOutcome = outcome;
    this.requestCount += 1;
    if (this.activeSession) {
      this.activeSession = await this.client.getSession(this.activeSession.session_id);
    }
    const summary = answerSummary(outcome.artifact.content);
    this.localConversation.push({ role: "user", text: requestText });
    this.localConversation.push({ role: "agent", text: summary, runId: outcome.run.run_id });
    if (this.debugEnabled) {
      console.log(renderDebugRun(outcome));
      console.log(renderDebugArtifact(outcome.artifact));
      console.log(renderEvaluation(outcome.evaluation));
    } else {
      console.log(renderAnswer(outcome.artifact.content));
      if (outcome.invocations.length > 1) {
        console.log("\n협업 실행");
        console.log("─────────");
        console.log(renderInvocations(outcome.invocations));
      }
    }
    const sessionText = this.activeSession ? ` · session turn ${this.activeSession.turn_count}` : "";
    console.log(`\n완료 · ${outcome.run.total_tokens} tokens${sessionText} · 다시 질문하거나 /details를 입력하세요.`);
  }
}
