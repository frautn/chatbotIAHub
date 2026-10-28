import assert from 'node:assert/strict';
import { test } from 'node:test';
import { percentile, validateConfig } from '../lib.mjs';
import { config, example } from './helpers.mjs';

test('example requires explicit selector calibration', () => {
  assert.throws(() => validateConfig(example, [{ username: 'student', password: 'secret' }]),
    /Configure and verify selectors.chatInput/);
});

test('validates identities, bounds, selectors and target origins', () => {
  const accounts = [{ username: 'student', password: 'secret' }];
  assert.doesNotThrow(() => validateConfig(config(), accounts));
  for (const overrides of [
    { users: 0 }, { users: 46 }, { users: 1.5 }, { rounds: 0 }, { timeoutMs: 1 },
    { thinkMs: -1 }, { headless: 'false' }, { prompt: '' },
    { activityUrl: 'https://unrelated.example/activity' },
    { moodleOrigin: 'https://moodle.example.com/subpath' },
    { toolOrigin: 'http://remote.example' },
    { toolOrigin: 'https://user:password@chat.example.com' },
  ]) {
    assert.throws(() => validateConfig(config(overrides), accounts));
  }
  assert.throws(() => validateConfig(config({ users: 2 }), accounts), /separate account/);
  assert.throws(() => validateConfig(config({ users: 2 }), [...accounts, ...accounts]), /distinct/);
  assert.throws(() => validateConfig(config({ users: 2 }),
    [...accounts, { username: 'STUDENT', password: 'secret' }]), /distinct/);
  assert.throws(() => validateConfig(config(), [{ username: 'student', password: '' }]), /password/);
  assert.doesNotThrow(() => validateConfig(config({ users: 30 }),
    Array.from({ length: 30 }, (_, index) => ({ username: `student-${index}`, password: 'secret' }))));
});

test('nearest-rank p95 does not mutate samples and handles empty data', () => {
  assert.equal(percentile([], 0.95), null);
  const samples = [4, 1, 3, 2];
  assert.equal(percentile(samples, 0.95), 4);
  assert.deepEqual(samples, [4, 1, 3, 2]);
  assert.equal(percentile(Array.from({ length: 100 }, (_, i) => i + 1), 0.95), 95);
});
