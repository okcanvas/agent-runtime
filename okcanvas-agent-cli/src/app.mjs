import { ServiceApiClient } from './api-client.mjs';
import { CliError } from './errors.mjs';
import { InteractiveLineSource, ScriptLineSource } from './line-source.mjs';
import { publicConfig } from './config.mjs';
import { renderArtifactContent, renderError, renderProgressEvent, renderRoute, renderSessions, shortId } from './render.mjs';

const HELP = `명령
  /help                    도움말
  /status                  Runtime·사용자·Session·Model 상태
  /whoami                  인증된 사용자 확인
  /capabilities            Runtime 제품 기능 확인
  /route <요청>            실행하지 않고 자동 라우팅만 확인
  /new                     새 Assistant Session 생성
  /session                 현재 Session 조회
  /sessions                내 Session 목록
  /resume <id|번호>        기존 Session 재개
  /clear                   현재 Session 기록 삭제
  /model <id|default>      모델 변경
  /events                  마지막 Run Event
  /details                 마지막 Run 상세
  /json                    마지막 최종 Artifact JSON
  /quit                    종료`;

export class ServiceAgentCli {
  constructor(config, {
    client = new ServiceApiClient(config),
    input = config.scriptFile ? new ScriptLineSource(config.scriptFile) : new InteractiveLineSource(),
    write = (line = '') => console.log(line),
  } = {}) {
    this.config = config;
    this.client = client;
    this.input = input;
    this.write = write;
    this.model = config.model;
    this.session = undefined;
    this.principal = undefined;
    this.capability = undefined;
    this.lastOutcome = undefined;
    this.requestCount = 0;
  }

  async initialize() {
    this.principal = await this.client.whoAmI();
    this.capability = await this.client.capabilities();
    if (this.config.sessionEnabled) {
      this.session = this.config.sessionId
        ? await this.client.getSession(this.config.sessionId)
        : await this.client.createAssistantSession();
      if (this.session.state !== 'ACTIVE') {
        throw new CliError('CLI_SESSION_NOT_ACTIVE', `Session is not ACTIVE: ${this.session.session_id}`);
      }
    }
  }

  prompt() {
    const principal = this.principal?.principal_id ?? 'user';
    const session = this.session ? ` [${shortId(this.session.session_id)}]` : '';
    return `\n${principal}${session}> `;
  }

  banner() {
    this.write('============================================================');
    this.write(' OKCanvas Agent Service CLI · Product HTTP/SSE Client');
    this.write('============================================================');
    this.write(`Runtime ${this.capability?.runtime_version ?? 'unknown'} · tenant ${this.principal?.tenant_id ?? '-'} · principal ${this.principal?.principal_id ?? '-'}`);
    this.write(`Session ${this.session ? shortId(this.session.session_id) : 'disabled'} · Model ${this.model ?? 'server default'}`);
    this.write('/help 명령으로 사용법을 확인하세요.');
  }

  async run() {
    try {
      await this.initialize();
      this.banner();
      while (true) {
        const raw = await this.input.next(this.prompt());
        if (raw === null) break;
        const line = raw.trim();
        if (!line) continue;
        try {
          if (line.startsWith('/')) {
            if (await this.command(line)) break;
          } else {
            await this.execute(line);
          }
        } catch (error) {
          this.write(renderError(error));
        }
      }
      this.write(`\n종료 · ${this.requestCount}개 요청 완료`);
      return 0;
    } finally {
      this.input.close();
    }
  }

  async command(line) {
    const [command, ...rest] = line.split(/\s+/u);
    const argument = rest.join(' ').trim();
    switch (command) {
      case '/quit': case '/exit': return true;
      case '/help': this.write(HELP); return false;
      case '/status': this.write(JSON.stringify({ ...publicConfig(this.config), model: this.model ?? null, principal: this.principal, session: this.session }, null, 2)); return false;
      case '/whoami': this.principal = await this.client.whoAmI(); this.write(JSON.stringify(this.principal, null, 2)); return false;
      case '/capabilities': this.capability = await this.client.capabilities(); this.write(JSON.stringify({
        runtime_version: this.capability.runtime_version,
        organization_assistant_routing_available: this.capability.organization_assistant_routing_available,
        organization_context_catalog_state: this.capability.organization_context_catalog_state,
        groupware_read_state: this.capability.groupware_read_state,
        groupware_read_executable_now: this.capability.groupware_read_executable_now,
      }, null, 2)); return false;
      case '/route': if (!argument) this.write('사용법: /route <요청>'); else this.write(JSON.stringify(await this.client.route(argument, this.session?.session_id), null, 2)); return false;
      case '/new': await this.newSession(); return false;
      case '/session': await this.showSession(); return false;
      case '/sessions': await this.showSessions(); return false;
      case '/resume': await this.resume(argument); return false;
      case '/clear': await this.clearSession(); return false;
      case '/model': this.setModel(argument); return false;
      case '/events': this.write(this.lastOutcome ? JSON.stringify(this.lastOutcome.events, null, 2) : '마지막 Run이 없습니다.'); return false;
      case '/details': this.write(this.lastOutcome ? JSON.stringify({ route: this.lastOutcome.route, run: this.lastOutcome.run, invocations: this.lastOutcome.invocations }, null, 2) : '마지막 Run이 없습니다.'); return false;
      case '/json': this.write(this.lastOutcome ? JSON.stringify(this.lastOutcome.artifact.content, null, 2) : '마지막 Artifact가 없습니다.'); return false;
      default: this.write(`알 수 없는 명령: ${command}`); return false;
    }
  }

  async newSession() {
    if (!this.config.sessionEnabled) { this.write('현재 --no-session 모드입니다.'); return; }
    this.session = await this.client.createAssistantSession();
    this.write(`새 Session: ${this.session.session_id}`);
  }

  async showSession() {
    if (!this.session) { this.write('활성 Session이 없습니다.'); return; }
    this.session = await this.client.getSession(this.session.session_id);
    this.write(JSON.stringify(this.session, null, 2));
  }

  async showSessions() {
    if (!this.config.sessionEnabled) { this.write('현재 --no-session 모드입니다.'); return; }
    const payload = await this.client.listSessions(200);
    this.write(renderSessions(payload, this.session?.session_id));
  }

  async resume(argument) {
    if (!this.config.sessionEnabled) { this.write('현재 --no-session 모드입니다.'); return; }
    if (!argument) { this.write('사용법: /resume <session-id|번호>'); return; }
    let sessionId = argument;
    if (/^\d+$/u.test(argument)) {
      const payload = await this.client.listSessions(200);
      const selected = payload.sessions?.[Number(argument) - 1];
      if (!selected) throw new CliError('CLI_SESSION_NOT_FOUND', `Session 번호가 없습니다: ${argument}`);
      sessionId = selected.session_id;
    }
    const session = await this.client.getSession(sessionId);
    if (session.state !== 'ACTIVE') throw new CliError('CLI_SESSION_NOT_ACTIVE', `Session is not ACTIVE: ${sessionId}`);
    this.session = session;
    this.write(`Session 재개: ${session.session_id}`);
  }

  async clearSession() {
    if (!this.session) { this.write('활성 Session이 없습니다.'); return; }
    this.session = await this.client.clearSession(this.session.session_id);
    this.write(`Session 기록 삭제: ${this.session.session_id}`);
  }

  setModel(argument) {
    if (!argument) { this.write(`현재 모델: ${this.model ?? 'server default'}`); return; }
    this.model = argument === 'default' ? undefined : argument;
    this.write(`모델: ${this.model ?? 'server default'}`);
  }

  async execute(input) {
    this.write('라우팅 및 실행 준비 중...');
    let progressStarted = false;
    const outcome = await this.client.executeAssistant(input, {
      model: this.model,
      sessionId: this.session?.session_id,
      onRoute: (route) => {
        this.write(`Route: ${renderRoute(route)}`);
        if (this.config.debug && Array.isArray(route.reasons)) this.write(`Reasons: ${route.reasons.join(', ')}`);
      },
      confirm: async ({ route }) => {
        if (this.config.assumeYes) return true;
        const answer = await this.input.next(`실행할까요? ${route.request_class}/${route.side_effect} [Y/n] `);
        return answer !== null && ['', 'y', 'yes'].includes(answer.trim().toLowerCase());
      },
      onEvent: (event) => {
        if (this.config.debug) {
          this.write(`[${event.sequence}] ${event.event_type} ${JSON.stringify(event.payload ?? {})}`);
          return;
        }
        const progress = renderProgressEvent(event);
        if (!progress) return;
        if (!progressStarted) { this.write('진행'); progressStarted = true; }
        this.write(`- ${progress}`);
      },
    });
    if (outcome.state === 'NOT_EXECUTED') {
      this.write(`실행되지 않음: ${renderRoute(outcome.route)}`);
      if (Array.isArray(outcome.route.reasons)) for (const reason of outcome.route.reasons) this.write(`- ${reason}`);
      return;
    }
    if (outcome.state === 'DECLINED') { this.write('실행을 취소했습니다.'); return; }
    if (outcome.run.status !== 'SUCCEEDED') {
      throw new CliError('CLI_RUN_FAILED', `Run ended in ${outcome.run.status}`);
    }
    this.lastOutcome = outcome;
    this.requestCount += 1;
    if (this.session) this.session = await this.client.getSession(this.session.session_id);
    this.write('');
    this.write(renderArtifactContent(outcome.artifact.content));
    this.write(`\n완료 · ${outcome.run.total_tokens ?? 0} tokens · run ${shortId(outcome.run.run_id)}`);
  }
}
