import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { promisify } from 'node:util';
import { test } from 'node:test';
import { config } from './helpers.mjs';

const execute = promisify(execFile);
const runner = new URL('../run.mjs', import.meta.url).pathname;

test('CLI validates before network access, requires model consent and redacts identities', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'chatbotiahub-load-'));
  try {
    const configPath = join(directory, 'config.json');
    await writeFile(configPath, JSON.stringify(config()));
    await writeFile(join(directory, 'accounts.local.json'),
      JSON.stringify([{ username: 'private-test-user', password: 'private-test-password' }]));
    const options = { env: { ...process.env, PLAYWRIGHT_BROWSERS_PATH: join(directory, 'no-browser') } };
    const result = await execute(process.execPath, [runner, '--config', configPath, '--dry-run'], options);
    const plan = JSON.parse(result.stdout).plan;
    assert.equal(plan.mode, 'launch');
    assert.equal(plan.maxPromptSubmissions, 0);
    assert.ok(!result.stdout.includes('private-test'));
    await assert.rejects(execute(process.execPath,
      [runner, '--config', configPath, '--mode', 'chat', '--dry-run'], options),
    error => error.code === 1 && error.stderr.includes('--allow-model-requests'));
    const chat = await execute(process.execPath, [runner, '--config', configPath,
      '--mode', 'chat', '--rounds', '3', '--allow-model-requests', '--dry-run'], options);
    assert.equal(JSON.parse(chat.stdout).plan.maxPromptSubmissions, 3);
    await assert.rejects(execute(process.execPath,
      [runner, '--config', configPath, '--users', '46', '--dry-run'], options),
    error => error.code === 1 && error.stderr.includes('users must be'));
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test('CLI image dry-run uses discovered turn totals and validates files before browser startup', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'chatbotiahub-image-cli-'));
  try {
    const configPath = join(directory, 'config.json');
    await writeFile(configPath, JSON.stringify(config({ users: 2, rounds: 99, imageDirectory: './data' })));
    await writeFile(join(directory, 'accounts.local.json'), JSON.stringify([
      { username: 'private-student1', password: 'secret' },
      { username: 'private-student2', password: 'secret' },
    ]));
    await mkdir(join(directory, 'data'));
    for (const name of ['private-student1-turn1-1.png', 'private-student1-turn1-2.jpg',
      'private-student1-turn2-1.jpg', 'private-student2-turn1-1.png']) {
      await writeFile(join(directory, 'data', name), 'synthetic image');
    }
    const options = { env: { ...process.env, PLAYWRIGHT_BROWSERS_PATH: join(directory, 'no-browser') } };
    const args = [runner, '--config', configPath, '--mode', 'chat', '--allow-model-requests', '--dry-run'];
    const result = await execute(process.execPath, args, options);
    const plan = JSON.parse(result.stdout).plan;
    assert.equal(plan.rounds, 2);
    assert.equal(plan.maxPromptSubmissions, 3);
    assert.ok(!result.stdout.includes('private-student'));
    assert.ok(!result.stdout.includes(directory));
    await assert.rejects(execute(process.execPath, [...args, '--rounds', '1'], options),
      error => error.code === 1 && error.stderr.includes('cannot override image-driven'));
    await rm(join(directory, 'data', 'private-student2-turn1-1.png'));
    await assert.rejects(execute(process.execPath, args, options),
      error => error.code === 1 && error.stderr.includes('No PNG/JPG image turns found for user 2') &&
        !error.stderr.includes('private-student'));
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
