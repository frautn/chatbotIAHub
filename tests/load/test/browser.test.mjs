import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { execFile } from 'node:child_process';
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { promisify } from 'node:util';
import { after, before, test } from 'node:test';
import { chromium } from 'playwright';
import { launchStudent, runWorkload } from '../lib.mjs';
import { config } from './helpers.mjs';

let browser;
let moodle;
let tool;
let moodleOrigin;
let toolOrigin;
let submissions = 0;
const logins = new Set();
const accounts = [
  { username: 'student-1', password: 'secret-1' },
  { username: 'student-2', password: 'secret-2' },
];

async function serve(handler) {
  const server = createServer(handler);
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  return server;
}

before(async () => {
  browser = await chromium.launch();
  tool = await serve((request, response) => {
    if (request.url.startsWith('/count')) {
      submissions++;
      if (request.url.includes('limited')) response.statusCode = 429;
      response.end('ok');
      return;
    }
    response.setHeader('Content-Type', 'text/html');
    response.end(`<textarea id="input"></textarea><button id="send">Send</button>
      <button id="busy" hidden>Stop</button><div id="messages"></div>
      <script>
        document.querySelector('#send').onclick = async () => {
          document.querySelector('#busy').hidden = false;
          await fetch(${JSON.stringify(request.url === '/limited' ? '/count?limited' : '/count')});
          setTimeout(() => {
            const message = document.createElement('div');
            message.className = 'assistant';
            message.textContent = ${JSON.stringify(request.url === '/empty' ? '' : 'Complete synthetic answer')};
            document.querySelector('#messages').append(message);
            ${request.url === '/error' ? `
              const error = document.createElement('div');
              error.className = 'chat-error';
              error.textContent = 'Synthetic generation error';
              document.body.append(error);
            ` : ''}
            ${request.url === '/stuck' ? '' : "document.querySelector('#busy').hidden = true;"}
          }, 350);
        };
      </script>`);
  });
  toolOrigin = `http://127.0.0.1:${tool.address().port}`;
  moodle = await serve(async (request, response) => {
    response.setHeader('Content-Type', 'text/html');
    if (request.url === '/login/index.php' && request.method === 'POST') {
      let body = '';
      for await (const chunk of request) body += chunk;
      const form = new URLSearchParams(body);
      if (!accounts.some(account => account.username === form.get('username') &&
        account.password === form.get('password'))) {
        response.end('Login failed');
        return;
      }
      logins.add(form.get('username'));
      response.writeHead(302, { Location: '/my', 'Set-Cookie': `user=${form.get('username')}; Path=/; HttpOnly` });
      response.end();
    } else if (request.url === '/login/index.php') {
      response.end(`<form method="post"><input id="username" name="username">
        <input id="password" name="password" type="password"><button id="loginbtn">Login</button></form>`);
    } else if (request.url === '/my') {
      response.end('Dashboard');
    } else if (request.url.startsWith('/activity')) {
      if (!request.headers.cookie?.includes('user=')) {
        response.writeHead(401);
        response.end('No session');
        return;
      }
      const target = new URL(request.url, 'http://localhost').searchParams.get('target') ?? '/';
      response.end(request.url.includes('iframe') ?
        `<iframe src="${toolOrigin}${target}"></iframe>` :
        `<a id="launch" target="${request.url.includes('same-tab') ? '_self' : '_blank'}"
          href="${toolOrigin}${target}">Launch activity</a>`);
    } else {
      response.writeHead(404);
      response.end('Not found');
    }
  });
  moodleOrigin = `http://127.0.0.1:${moodle.address().port}`;
});

after(async () => {
  await browser?.close();
  for (const server of [moodle, tool]) {
    if (server) {
      server.closeAllConnections();
      await new Promise(resolve => server.close(resolve));
    }
  }
});

function fixtureConfig(overrides = {}) {
  return config({
    moodleOrigin, toolOrigin, activityUrl: `${moodleOrigin}/activity`,
    users: 2, rounds: 2, launchIntervalMs: 0, thinkMs: 0, timeoutMs: 2000,
    ...overrides,
  });
}

test('single login reaches the launched tool origin', async () => {
  const context = await browser.newContext();
  try {
    const frame = await launchStudent(context,
      fixtureConfig({ moodleOrigin: `${moodleOrigin}/`, toolOrigin: `${toolOrigin}/` }), accounts[0]);
    assert.equal(new URL(frame.url()).origin, toolOrigin);
  } finally {
    await context.close();
  }
});

test('real browser contexts log in independently, launch popups and finish all chat rounds', async () => {
  submissions = 0;
  logins.clear();
  const result = await runWorkload(browser, fixtureConfig(), accounts, 'chat');
  assert.equal(result.passed, true);
  assert.equal(result.completedChats, 4);
  assert.equal(submissions, 4);
  assert.equal(logins.size, 2);
  assert.equal(browser.contexts().length, 0);
  assert.ok(result.completionP95Ms >= 350);
  const report = JSON.stringify(result);
  for (const account of accounts) {
    assert.ok(!report.includes(account.username));
    assert.ok(!report.includes(account.password));
  }
});

test('launch mode handles embedded tools without submitting prompts', async () => {
  submissions = 0;
  const settings = fixtureConfig({ activityUrl: `${moodleOrigin}/activity?iframe` });
  settings.selectors.launch = null;
  const result = await runWorkload(browser, settings, accounts, 'launch');
  assert.equal(result.passed, true);
  assert.equal(result.completedChats, 0);
  assert.equal(submissions, 0);
});

test('launch mode supports same-tab tool navigation', async () => {
  const result = await runWorkload(browser,
    fixtureConfig({ activityUrl: `${moodleOrigin}/activity?same-tab` }), accounts, 'launch');
  assert.equal(result.passed, true);
});

test('failed login prevents the entire cohort from sending paid prompts', async () => {
  submissions = 0;
  const result = await runWorkload(browser, fixtureConfig(),
    [accounts[0], { ...accounts[1], password: 'incorrect' }], 'chat');
  assert.equal(result.passed, false);
  assert.equal(result.failedJourneys, 1);
  assert.equal(result.completedChats, 0);
  assert.equal(submissions, 0);
  assert.equal(browser.contexts().length, 0);
});

test('empty assistant messages fail instead of reporting stream success', async () => {
  const result = await runWorkload(browser,
    fixtureConfig({ activityUrl: `${moodleOrigin}/activity?target=/empty` }), accounts, 'chat');
  assert.equal(result.passed, false);
  assert.equal(result.completedChats, 0);
  assert.equal(result.events.filter(event => event.phase === 'chat').length, 2);
});

test('a stream that never finishes times out and stops subsequent rounds', async () => {
  const result = await runWorkload(browser,
    fixtureConfig({ activityUrl: `${moodleOrigin}/activity?target=/stuck` }), accounts, 'chat');
  assert.equal(result.passed, false);
  assert.equal(result.completedChats, 0);
  assert.equal(result.events.filter(event => event.phase === 'chat').length, 2);
});

test('visible generation errors cannot pass as assistant responses', async () => {
  const result = await runWorkload(browser,
    fixtureConfig({ activityUrl: `${moodleOrigin}/activity?target=/error` }), accounts, 'chat');
  assert.equal(result.passed, false);
  assert.equal(result.completedChats, 0);
});

test('HTTP rate-limit responses fail the run even if the UI looks complete', async () => {
  const result = await runWorkload(browser,
    fixtureConfig({ activityUrl: `${moodleOrigin}/activity?target=/limited` }), accounts, 'chat');
  assert.equal(result.passed, false);
  assert.equal(result.completedChats, 2);
  assert.equal(result.httpErrors[429], 2);
});

test('CLI persists sanitized success and failure reports with matching exit status', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'chatbotiahub-report-'));
  const execute = promisify(execFile);
  const runner = new URL('../run.mjs', import.meta.url).pathname;
  try {
    await writeFile(join(directory, 'config.json'), JSON.stringify(fixtureConfig({ users: 1 })));
    await writeFile(join(directory, 'accounts.local.json'), JSON.stringify(accounts));
    const success = await execute(process.execPath, [runner, '--config', 'config.json'], { cwd: directory });
    assert.ok(success.stdout.includes('"passed": true'));
    await writeFile(join(directory, 'accounts.local.json'),
      JSON.stringify([{ ...accounts[0], password: 'wrong-password' }]));
    await assert.rejects(execute(process.execPath, [runner, '--config', 'config.json'], { cwd: directory }),
      error => error.code === 1 && error.stdout.includes('"passed": false'));
    const reports = await readdir(join(directory, 'results'));
    assert.equal(reports.length, 2);
    for (const filename of reports) {
      const contents = await readFile(join(directory, 'results', filename), 'utf8');
      const report = JSON.parse(contents);
      assert.equal(report.schemaVersion, 1);
      assert.equal(report.users, 1);
      assert.equal(report.events.length, 1);
      assert.ok(!contents.includes(accounts[0].username));
      assert.ok(!contents.includes('wrong-password'));
    }
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
