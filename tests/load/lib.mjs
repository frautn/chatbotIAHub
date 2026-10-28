import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { performance } from 'node:perf_hooks';
import { setTimeout as sleep } from 'node:timers/promises';

export class ConfigurationError extends Error {}

function requireValue(condition, message) {
  if (!condition) throw new ConfigurationError(message);
}

function validUrl(value) {
  const url = new URL(value);
  requireValue(!url.username && !url.password, 'URLs must not contain credentials.');
  requireValue(url.protocol === 'https:' ||
    (url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)),
  'Use HTTPS except for local fixture tests.');
  return url;
}

export function validateConfig(config, accounts) {
  const moodle = validUrl(config.moodleOrigin);
  const tool = validUrl(config.toolOrigin);
  requireValue(moodle.href === `${moodle.origin}/` && tool.href === `${tool.origin}/`,
    'moodleOrigin and toolOrigin must be origins without paths.');
  requireValue(validUrl(config.activityUrl).origin === moodle.origin,
    'activityUrl must belong to moodleOrigin.');
  for (const [key, min, max] of [
    ['users', 1, 45], ['rounds', 1, 1000], ['launchIntervalMs', 0, 60000],
    ['thinkMs', 0, 3600000], ['timeoutMs', 1000, 600000],
  ]) {
    requireValue(Number.isInteger(config[key]) && config[key] >= min && config[key] <= max,
      `${key} must be an integer between ${min} and ${max}.`);
  }
  requireValue(typeof config.headless === 'boolean', 'headless must be boolean.');
  requireValue(typeof config.prompt === 'string' && config.prompt.trim().length > 0,
    'A nonempty synthetic prompt is required.');
  for (const key of ['username', 'password', 'login', 'chatInput', 'send', 'busy', 'assistantMessage', 'chatError']) {
    requireValue(typeof config.selectors?.[key] === 'string' &&
      config.selectors[key].trim() && !config.selectors[key].includes('REPLACE_'),
    `Configure and verify selectors.${key}.`);
  }
  requireValue(config.selectors.launch === null ||
    (typeof config.selectors.launch === 'string' && config.selectors.launch.trim()),
  'selectors.launch must be null or a selector.');
  requireValue(Array.isArray(accounts) && accounts.length >= config.users,
    'Provide at least one separate account per user.');
  const selected = accounts.slice(0, config.users);
  requireValue(selected.every(account => typeof account?.username === 'string' &&
    account.username.trim() && typeof account.password === 'string' &&
    account.password.length > 0 && !account.password.includes('REPLACE_')),
  'Every selected account needs a test username and password.');
  requireValue(new Set(selected.map(account => account.username.trim().toLowerCase())).size === selected.length,
    'Selected usernames must be distinct.');
  return config;
}

export async function readConfig(path, overrides = {}) {
  const config = { ...JSON.parse(await readFile(path, 'utf8')), ...overrides };
  requireValue(typeof config.accountsFile === 'string', 'accountsFile is required.');
  const accounts = JSON.parse(await readFile(resolve(dirname(path), config.accountsFile), 'utf8'));
  validateConfig(config, accounts);
  return { config, accounts: accounts.slice(0, config.users) };
}

export function percentile(values, fraction) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.ceil(sorted.length * fraction) - 1];
}

async function findChat(context, config) {
  const deadline = performance.now() + config.timeoutMs;
  while (performance.now() < deadline) {
    for (const page of context.pages()) {
      for (const frame of page.frames()) {
        if (new URL(frame.url(), config.moodleOrigin).origin === new URL(config.toolOrigin).origin &&
          await frame.locator(config.selectors.chatInput).isVisible()) return frame;
      }
    }
    await sleep(100);
  }
  throw new Error('Chat did not become ready.');
}

export async function launchStudent(context, config, account) {
  const page = await context.newPage();
  page.setDefaultTimeout(config.timeoutMs);
  page.setDefaultNavigationTimeout(config.timeoutMs);
  await page.goto(new URL('/login/index.php', config.moodleOrigin).href);
  await page.locator(config.selectors.username).fill(account.username);
  await page.locator(config.selectors.password).fill(account.password);
  await Promise.all([
    page.waitForURL(url => url.origin === new URL(config.moodleOrigin).origin &&
      !url.pathname.startsWith('/login/')),
    page.locator(config.selectors.login).click(),
  ]);
  await page.goto(config.activityUrl);
  if (config.selectors.launch) await page.locator(config.selectors.launch).click();
  return findChat(context, config);
}

export async function sendPrompt(frame, config) {
  const { selectors, timeoutMs } = config;
  const messages = frame.locator(selectors.assistantMessage);
  const before = await messages.count();
  const input = frame.locator(selectors.chatInput);
  const busy = frame.locator(selectors.busy);
  const errors = frame.locator(selectors.chatError).filter({ visible: true });
  requireValue(await errors.count() === 0, 'Chat has a visible error before submission.');
  await input.fill(config.prompt);
  const start = performance.now();
  // Arm before clicking; never equate HTTP 200 or first text with stream completion.
  const started = busy.waitFor({ state: 'visible', timeout: timeoutMs });
  const clicked = frame.locator(selectors.send).click({ timeout: timeoutMs });
  await Promise.all([started, clicked]);
  await busy.waitFor({ state: 'hidden', timeout: timeoutMs });
  requireValue(await errors.count() === 0, 'Chat reported a visible generation error.');
  const reply = messages.nth(before);
  await reply.waitFor({ state: 'visible', timeout: timeoutMs });
  requireValue((await reply.innerText()).trim().length > 0, 'Empty assistant response.');
  return { completionMs: Math.round(performance.now() - start) };
}

export async function runWorkload(browser, config, accounts, mode) {
  const contexts = [];
  const events = [];
  const httpErrors = {};
  const hasServiceErrors = () => Object.keys(httpErrors)
    .some(status => Number(status) === 429 || Number(status) >= 500);
  const start = performance.now();
  let infrastructureError = false;
  try {
    const students = await Promise.all(accounts.map(async (account, index) => {
      let phase = 'context';
      const event = { user: index + 1, phase: 'launch', ok: false };
      events.push(event);
      try {
        await sleep(index * config.launchIntervalMs);
        const context = await browser.newContext();
        contexts.push(context);
        context.setDefaultTimeout(config.timeoutMs);
        context.on('response', response => {
          if (response.status() >= 400) {
            httpErrors[response.status()] = (httpErrors[response.status()] ?? 0) + 1;
          }
        });
        phase = 'login-or-lti';
        const started = performance.now();
        const frame = await launchStudent(context, config, account);
        event.ok = true;
        event.durationMs = Math.round(performance.now() - started);
        return { frame, user: index + 1 };
      } catch (error) {
        event.error = phase;
        event.failure = error.name === 'TimeoutError' ? 'timeout' : 'browser-or-validation';
        return null;
      }
    }));
    // Fail closed: an incomplete cohort must not generate a misleading load result.
    if (mode === 'chat' && students.every(Boolean) && !hasServiceErrors()) {
      for (let round = 1; round <= config.rounds; round++) {
        const results = await Promise.all(students.map(async ({ frame, user }) => {
          const event = { user, phase: 'chat', round, ok: false };
          events.push(event);
          try {
            Object.assign(event, await sendPrompt(frame, config), { ok: true });
          } catch (error) {
            event.error = 'send-or-stream-completion';
            event.failure = error.name === 'TimeoutError' ? 'timeout' : 'browser-or-validation';
          }
          return event.ok;
        }));
        if (!results.every(Boolean) || hasServiceErrors()) break;
        if (round < config.rounds) await sleep(config.thinkMs);
      }
    }
  } finally {
    const closed = await Promise.allSettled(contexts.map(context => context.close()));
    infrastructureError = closed.some(result => result.status === 'rejected');
  }
  const chats = events.filter(event => event.phase === 'chat');
  const failed = events.filter(event => !event.ok).length;
  const expectedChats = mode === 'chat' ? config.users * config.rounds : 0;
  return {
    schemaVersion: 1,
    mode,
    users: config.users,
    rounds: mode === 'chat' ? config.rounds : 0,
    maxPromptSubmissions: expectedChats,
    durationMs: Math.round(performance.now() - start),
    passed: !infrastructureError && failed === 0 && chats.length === expectedChats &&
      !hasServiceErrors(),
    infrastructureError,
    failedJourneys: failed,
    completedChats: chats.filter(event => event.ok).length,
    launchP95Ms: percentile(events.filter(event => event.phase === 'launch' && event.ok)
      .map(event => event.durationMs), 0.95),
    completionP95Ms: percentile(chats.filter(event => event.ok)
      .map(event => event.completionMs), 0.95),
    httpErrors,
    events,
  };
}
