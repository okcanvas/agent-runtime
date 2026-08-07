export function shortId(value) {
  if (typeof value !== 'string') return '-';
  return value.length <= 18 ? value : `${value.slice(0, 10)}…${value.slice(-6)}`;
}

export function renderRoute(route) {
  const agent = route.selected_agent_definition_id ?? 'none';
  return `${route.request_class ?? 'UNKNOWN'} · ${route.status ?? 'UNKNOWN'} · agent ${agent}`;
}

export function renderProgressEvent(event) {
  const type = String(event.event_type ?? 'event');
  const labels = {
    'run.started': 'Run 시작',
    'agent.started': 'Agent 시작',
    'model.started': '모델 요청',
    'model.completed': '모델 응답',
    'tool.started': 'Tool 시작',
    'tool.completed': 'Tool 완료',
    'artifact.created': '최종 결과 저장',
    'run.completed': 'Run 완료',
    'run.failed': 'Run 실패',
    'run.cancelled': 'Run 취소',
  };
  return labels[type] ?? (type.includes('completed') || type.includes('started') ? type : null);
}

function stringList(value) {
  return Array.isArray(value) ? value.filter((item) => typeof item === 'string') : [];
}

export function renderArtifactContent(content) {
  if (!content || typeof content !== 'object' || Array.isArray(content)) return String(content ?? '');
  const primary = ['answer', 'summary', 'text', 'output', 'message']
    .map((key) => content[key])
    .find((value) => typeof value === 'string' && value.trim());
  const lines = primary ? [primary.trim()] : [JSON.stringify(content, null, 2)];
  const citations = Array.isArray(content.citations) ? content.citations : [];
  if (citations.length > 0) {
    lines.push('', '근거');
    for (const item of citations) {
      if (!item || typeof item !== 'object') continue;
      lines.push(`- ${String(item.label ?? item.title ?? 'source')}${item.reference ? ` (${item.reference})` : ''}`);
    }
  }
  const unverified = stringList(content.unverified);
  if (unverified.length > 0) {
    lines.push('', '미확인');
    for (const item of unverified) lines.push(`- ${item}`);
  }
  return lines.join('\n');
}

export function renderSessions(payload, activeSessionId) {
  const sessions = Array.isArray(payload?.sessions) ? payload.sessions : [];
  if (sessions.length === 0) return 'Session이 없습니다.';
  return sessions.map((session, index) => {
    const active = session.session_id === activeSessionId ? '*' : ' ';
    return `${active} ${index + 1}. ${shortId(session.session_id)} · ${session.state} · turns ${session.turn_count}`;
  }).join('\n');
}

export function renderError(error) {
  const code = typeof error?.code === 'string' ? error.code : 'CLI_UNEXPECTED_ERROR';
  const message = error instanceof Error ? error.message : String(error);
  return `[${code}] ${message}`;
}
