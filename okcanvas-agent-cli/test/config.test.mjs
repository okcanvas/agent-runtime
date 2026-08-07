import assert from 'node:assert/strict';
import test from 'node:test';
import { parseCliConfig, publicConfig } from '../src/config.mjs';

test('config accepts external bearer and does not expose it publicly', () => {
  const config = parseCliConfig(['--base-url', 'http://localhost:8765/', '--yes'], { OKCANVAS_SERVICE_BEARER: 'top-secret' });
  assert.equal(config.baseUrl, 'http://localhost:8765');
  assert.equal(config.assumeYes, true);
  assert.equal(config.bearer, 'top-secret');
  assert.equal(JSON.stringify(publicConfig(config)).includes('top-secret'), false);
});

test('config rejects missing bearer and incompatible session flags', () => {
  assert.throws(() => parseCliConfig([], {}), /OKCANVAS_SERVICE_BEARER/u);
  assert.throws(() => parseCliConfig(['--bearer', 'x', '--session-id', 'session_x', '--no-session'], {}), /cannot be combined/u);
});
