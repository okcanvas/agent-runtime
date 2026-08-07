import assert from 'node:assert/strict';
import test from 'node:test';
import { parseSseJson } from '../src/sse.mjs';

test('persisted SSE parser handles split UTF-8 chunks and heartbeats', async () => {
  const encoded = new TextEncoder().encode(': heartbeat\n\nid: 1\ndata: {"run_id":"run-1","sequence":1,"event_type":"상태 → 완료"}\n\n');
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoded.slice(0, 17));
      controller.enqueue(encoded.slice(17));
      controller.close();
    },
  });
  const events = [];
  for await (const event of parseSseJson(stream)) events.push(event);
  assert.equal(events.length, 1);
  assert.equal(events[0].event_type, '상태 → 완료');
});
