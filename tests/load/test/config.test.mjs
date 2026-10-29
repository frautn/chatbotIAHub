import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { percentile, readConfig, readImageTurns, validateConfig, workloadPlan } from '../lib.mjs';
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
    { imageDirectory: '' }, { imageDirectory: 1 },
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

test('image discovery groups exact usernames, sorts numerically and plans unequal turns', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'load-images-'));
  const accounts = [{ username: 'student.1', password: 'secret' }, { username: 'student', password: 'secret' }];
  try {
    const data = join(directory, 'data', 'thermodynamics');
    await mkdir(data, { recursive: true });
    for (const name of ['student.1-turn1-10.jpg', 'student.1-turn1-2.png',
      'student.1-turn2-1.PNG', 'student-turn1-1.jpg', 'studentX1-turn3-1.png',
      'student.1-turn1-3.gif']) {
      await writeFile(join(data, name), 'synthetic image');
    }
    await writeFile(join(directory, 'accounts.local.json'), JSON.stringify(accounts));
    const path = join(directory, 'config.json');
    await writeFile(path, JSON.stringify(config({ users: 2, rounds: 99, imageDirectory: './data/thermodynamics' })));
    const { config: settings } = await readConfig(path);
    assert.deepEqual(settings.imageTurns, [
      [[join(data, 'student.1-turn1-2.png'), join(data, 'student.1-turn1-10.jpg')],
        [join(data, 'student.1-turn2-1.PNG')]],
      [[join(data, 'student-turn1-1.jpg')]],
    ]);
    assert.equal(workloadPlan(settings, 'chat').maxPromptSubmissions, 3);
    assert.equal(workloadPlan(settings, 'chat').rounds, 2);
    assert.equal(workloadPlan(settings, 'launch').maxPromptSubmissions, 0);
    await assert.rejects(readConfig(path, { rounds: 1 }), /cannot override/);
    const { config: selected } = await readConfig(path, { users: 1 });
    assert.equal(selected.imageTurns.length, 1);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test('image preflight rejects missing, empty, duplicate, non-file and noncontiguous image turns', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'load-images-invalid-'));
  const accounts = [{ username: 'student', password: 'secret' }];
  try {
    await assert.rejects(readImageTurns(join(directory, 'missing'), accounts), /Cannot read imageDirectory/);
    await assert.rejects(readImageTurns(directory, accounts), /No PNG\/JPG/);
    const first = join(directory, 'student-turn1-1.png');
    await writeFile(first, '');
    await assert.rejects(readImageTurns(directory, accounts), /Empty image/);
    await writeFile(first, 'image');
    const duplicate = join(directory, 'student-turn1-1.jpg');
    await writeFile(duplicate, 'image');
    await assert.rejects(readImageTurns(directory, accounts), /Duplicate image index/);
    await rm(duplicate);
    const gap = join(directory, 'student-turn3-1.png');
    await writeFile(gap, 'image');
    await assert.rejects(readImageTurns(directory, accounts), /without gaps/);
    await rm(gap);
    await mkdir(join(directory, 'student-turn2-1.jpg'));
    await assert.rejects(readImageTurns(directory, accounts), /regular file/);
    const settings = config({ imageDirectory: directory });
    settings.selectors.fileInput = 'REPLACE_FILE_INPUT';
    assert.throws(() => validateConfig(settings, accounts), /selectors.fileInput/);
    settings.selectors.fileInput = '#files';
    settings.selectors.attachmentReady = '';
    assert.throws(() => validateConfig(settings, accounts), /selectors.attachmentReady/);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test('nearest-rank p95 does not mutate samples and handles empty data', () => {
  assert.equal(percentile([], 0.95), null);
  const samples = [4, 1, 3, 2];
  assert.equal(percentile(samples, 0.95), 4);
  assert.deepEqual(samples, [4, 1, 3, 2]);
  assert.equal(percentile(Array.from({ length: 100 }, (_, i) => i + 1), 0.95), 95);
});
