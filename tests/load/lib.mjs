import { readFile, readdir } from 'node:fs/promises';
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
  requireValue(config.imageDirectory == null ||
    (typeof config.imageDirectory === 'string' && config.imageDirectory.trim().length > 0),
  'imageDirectory must be null or a nonempty directory path.');
  if (config.imageDirectory != null) {
    for (const key of ['fileInput', 'attachmentReady']) {
      requireValue(typeof config.selectors?.[key] === 'string' &&
        config.selectors[key].trim() && !config.selectors[key].includes('REPLACE_'),
      `Configure and verify selectors.${key}.`);
    }
  }
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

export async function readImageTurns(directory, accounts) {
  let entries;
  try {
    entries = await readdir(directory, { withFileTypes: true });
  } catch {
    throw new ConfigurationError('Cannot read imageDirectory.');
  }
  return Promise.all(accounts.map(async (account, user) => {
    const turns = new Map();
    for (const entry of entries) {
      const prefix = `${account.username}-turn`;
      if (!entry.name.startsWith(prefix)) continue;
      const match = /^([1-9]\d*)-([1-9]\d*)\.(png|jpg)$/i.exec(entry.name.slice(prefix.length));
      if (!match) continue;
      requireValue(entry.isFile(), `Image entry for user ${user + 1} must be a regular file.`);
      const turn = Number(match[1]);
      const index = Number(match[2]);
      requireValue(Number.isSafeInteger(turn) && turn <= 1000 && Number.isSafeInteger(index),
        `Image turn/index for user ${user + 1} is out of range.`);
      if (!turns.has(turn)) turns.set(turn, new Map());
      requireValue(!turns.get(turn).has(index),
        `Duplicate image index for user ${user + 1}, turn ${turn}.`);
      const path = resolve(directory, entry.name);
      let contents;
      try {
        contents = await readFile(path);
      } catch {
        throw new ConfigurationError(`Cannot read image for user ${user + 1}, turn ${turn}.`);
      }
      requireValue(contents.length > 0, `Empty image for user ${user + 1}, turn ${turn}.`);
      turns.get(turn).set(index, path);
    }
    requireValue(turns.size > 0, `No PNG/JPG image turns found for user ${user + 1}.`);
    const ordered = [...turns].sort(([a], [b]) => a - b);
    requireValue(ordered.every(([turn], index) => turn === index + 1),
      `Image turns for user ${user + 1} must start at 1 without gaps.`);
    return ordered.map(([, images]) => [...images].sort(([a], [b]) => a - b).map(([, path]) => path));
  }));
}

export async function readConfig(path, overrides = {}) {
  const config = { ...JSON.parse(await readFile(path, 'utf8')), ...overrides };
  requireValue(typeof config.accountsFile === 'string', 'accountsFile is required.');
  const accounts = JSON.parse(await readFile(resolve(dirname(path), config.accountsFile), 'utf8'));
  validateConfig(config, accounts);
  const selected = accounts.slice(0, config.users);
  if (config.imageDirectory != null) {
    requireValue(overrides.rounds === undefined, '--rounds cannot override image-driven turns.');
    config.imageTurns = await readImageTurns(resolve(dirname(path), config.imageDirectory), selected);
  }
  return { config, accounts: selected };
}

export function workloadPlan(config, mode) {
  return {
    mode,
    users: config.users,
    rounds: mode === 'chat' ?
      (config.imageTurns ? Math.max(...config.imageTurns.map(turns => turns.length)) : config.rounds) : 0,
    maxPromptSubmissions: mode === 'chat' ?
      (config.imageTurns ? config.imageTurns.reduce((sum, turns) => sum + turns.length, 0) :
        config.users * config.rounds) : 0,
    launchIntervalMs: config.launchIntervalMs,
    thinkMs: config.thinkMs,
  };
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

export async function sendPrompt(frame, config, images = []) {
  const { selectors, timeoutMs } = config;
  const messages = frame.locator(selectors.assistantMessage);
  const before = await messages.count();
  const input = frame.locator(selectors.chatInput);
  const busy = frame.locator(selectors.busy);
  const errors = frame.locator(selectors.chatError).filter({ visible: true });
  requireValue(await errors.count() === 0, 'Chat has a visible error before submission.');
  await input.fill(config.prompt);
  if (images.length) {
    const attachments = frame.locator(selectors.attachmentReady);
    requireValue(await attachments.count() === 0, 'Composer contains unexpected ready attachments.');
    await frame.locator(selectors.fileInput).setInputFiles(images, { timeout: timeoutMs });
    await attachments.nth(images.length - 1).waitFor({ state: 'visible', timeout: timeoutMs });
    requireValue(await attachments.count() === images.length, 'Unexpected number of ready attachments.');
    requireValue(await errors.count() === 0, 'Chat reported a visible upload error.');
  }
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
  const plan = workloadPlan(config, mode);
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
        return { frame, user: index + 1, imageTurns: config.imageTurns?.[index] };
      } catch (error) {
        event.error = phase;
        event.failure = error.name === 'TimeoutError' ? 'timeout' : 'browser-or-validation';
        return null;
      }
    }));
    // Fail closed: an incomplete cohort must not generate a misleading load result.
    if (mode === 'chat' && students.every(Boolean) && !hasServiceErrors()) {
      for (let round = 1; round <= plan.rounds; round++) {
        const active = students.filter(student => !student.imageTurns || round <= student.imageTurns.length);
        const results = await Promise.all(active.map(async ({ frame, user, imageTurns }) => {
          const event = { user, phase: 'chat', round, ok: false };
          events.push(event);
          try {
            Object.assign(event, await sendPrompt(frame, config, imageTurns?.[round - 1]), { ok: true });
          } catch (error) {
            event.error = 'send-or-stream-completion';
            event.failure = error.name === 'TimeoutError' ? 'timeout' : 'browser-or-validation';
          }
          return event.ok;
        }));
        if (!results.every(Boolean) || hasServiceErrors()) break;
        if (round < plan.rounds) await sleep(config.thinkMs);
      }
    }
  } finally {
    const closed = await Promise.allSettled(contexts.map(context => context.close()));
    infrastructureError = closed.some(result => result.status === 'rejected');
  }
  const chats = events.filter(event => event.phase === 'chat');
  const failed = events.filter(event => !event.ok).length;
  const expectedChats = plan.maxPromptSubmissions;
  return {
    schemaVersion: 1,
    mode,
    users: config.users,
    rounds: plan.rounds,
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
