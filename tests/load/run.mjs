import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { parseArgs } from 'node:util';
import { chromium } from 'playwright';
import { ConfigurationError, readConfig, runWorkload } from './lib.mjs';

let phase = 'configuration';

async function main() {
  const { values } = parseArgs({
    options: {
      config: { type: 'string', default: 'config.local.json' },
      mode: { type: 'string', default: 'launch' },
      users: { type: 'string' },
      rounds: { type: 'string' },
      'allow-model-requests': { type: 'boolean', default: false },
      'dry-run': { type: 'boolean', default: false },
      help: { type: 'boolean', default: false },
    },
  });
  if (values.help) {
    console.log('npm run load -- [--config config.local.json] [--mode launch|chat] [--users 1..45] [--rounds 1..1000] [--dry-run] [--allow-model-requests]');
    return;
  }
  if (!['launch', 'chat'].includes(values.mode)) throw new ConfigurationError('mode must be launch or chat.');
  const overrides = {};
  for (const key of ['users', 'rounds']) {
    if (values[key] !== undefined) overrides[key] = Number(values[key]);
  }
  const { config, accounts } = await readConfig(resolve(values.config), overrides);
  if (values.mode === 'chat' && !values['allow-model-requests']) {
    throw new ConfigurationError('Chat mode requires --allow-model-requests and an agreed provider-spend limit.');
  }
  const plan = {
    mode: values.mode,
    users: config.users,
    rounds: values.mode === 'chat' ? config.rounds : 0,
    maxPromptSubmissions: values.mode === 'chat' ? config.users * config.rounds : 0,
    launchIntervalMs: config.launchIntervalMs,
    thinkMs: config.thinkMs,
  };
  console.log(JSON.stringify({ plan }, null, 2));
  if (values['dry-run']) return;
  phase = 'browser-startup';
  const browser = await chromium.launch({ headless: config.headless });
  let summary;
  try {
    phase = 'workload';
    summary = await runWorkload(browser, config, accounts, values.mode);
    phase = 'browser-cleanup';
  } finally {
    await browser.close();
  }
  phase = 'report-writing';
  await mkdir('results', { recursive: true, mode: 0o700 });
  const path = resolve('results', `${new Date().toISOString().replaceAll(':', '-')}.json`);
  await writeFile(path, `${JSON.stringify(summary, null, 2)}\n`, { mode: 0o600, flag: 'wx' });
  console.log(JSON.stringify({ ...summary, events: undefined, report: path }, null, 2));
  if (!summary.passed) process.exitCode = 1;
}

main().catch(error => {
  // Browser errors can contain credentials, URLs, prompts and page contents.
  console.error(error instanceof ConfigurationError ? error.message :
    `Load test could not finish during ${phase}. Check JSON files, CLI options, browser installation and output permissions. Raw errors are suppressed to protect credentials; no successful result is claimed.`);
  process.exitCode = 1;
});
