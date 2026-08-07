import { CliError } from './errors.mjs';

export async function* parseSseJson(stream) {
  if (!stream || typeof stream.getReader !== 'function') {
    throw new CliError('CLI_SSE_RESPONSE_INVALID', 'SSE response has no readable body');
  }
  const reader = stream.getReader();
  const decoder = new TextDecoder('utf-8', { fatal: false });
  let buffer = '';
  let dataLines = [];

  const dispatch = () => {
    if (dataLines.length === 0) return null;
    const raw = dataLines.join('\n');
    dataLines = [];
    let payload;
    try {
      payload = JSON.parse(raw);
    } catch {
      throw new CliError('CLI_SSE_DATA_INVALID', 'Runtime SSE returned invalid JSON');
    }
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
      throw new CliError('CLI_SSE_DATA_INVALID', 'Runtime SSE returned a non-object payload');
    }
    return payload;
  };

  while (true) {
    const { done, value } = await reader.read();
    if (value) buffer += decoder.decode(value, { stream: !done });
    const lines = buffer.split(/\r?\n/u);
    buffer = done ? '' : (lines.pop() ?? '');
    for (const line of lines) {
      if (line === '') {
        const event = dispatch();
        if (event) yield event;
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).replace(/^ /u, ''));
      }
    }
    if (done) break;
  }
  buffer += decoder.decode();
  if (buffer) {
    for (const line of buffer.split(/\r?\n/u)) {
      if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /u, ''));
    }
  }
  const finalEvent = dispatch();
  if (finalEvent) yield finalEvent;
}
