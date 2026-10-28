import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
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
