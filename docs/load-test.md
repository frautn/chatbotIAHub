Ask User
Completed with input: {
  "question": "I recommend a Playwright-based student-journey harness with isolated identities, staged 5/15/30-user runs, and explicit opt-in for paid model requests. For its first version, how should test users authenticate?",
  "choices": [
    "Reuse separately saved student browser sessions; test chat capacity first (Recommended)",
    "Automate real Moodle login and LTI launches end to end",
    "Use a test-only LTI platform to exercise Gateway launches without Moodle"
  ]
}

Read 
Completed with input: {
  "path": "/home/edg/chatbotIAHub/docker/nginx-lti.example.conf"
}

Read 
Completed with input: {
  "path": "/home/edg/chatbotIAHub/.gitignore"
}

Read 
Completed with input: {
  "path": "/home/edg/chatbotIAHub/docker/nginx-lti11.example.conf"
}

Find files matching `**/{AGENTS.md,package.json,package-lock.json,.gitignore,*playwright*,tasks.json}`

Ran terminal command: git --no-pager status --short; node --version; npm --version

Ask User
Completed with input: {
  "question": "Does the Moodle test site use the standard username/password login form, or does login go through an external identity provider or MFA?",
  "choices": [
    "Standard Moodle username/password form",
    "External single sign-on (Google, Microsoft, institutional login)",
    "Username/password plus MFA"
  ]
}

I’ll add an isolated Playwright harness for real Moodle login and LTI launches, with separate browser sessions per student and an explicit opt-in for model requests. The custom chat UI isn’t in this repository, so its selectors will be configurable; I’ll validate the harness locally without contacting your deployment.


Read , lines 431 to 461
Completed with input: {
  "path": "/home/edg/chatbotIAHub/docs/scaling.md",
  "view_range": [
    431,
    461
  ]
}

Track load harness implementation
Completed with input: {
  "description": "Track load harness implementation",
  "query": "INSERT INTO todos(id,title,status,description) VALUES ('load-harness','Creating browser load harness','in_progress','Add an isolated Playwright harness for standard Moodle login, real LTI launches, synchronized chat rounds, explicit paid traffic consent and sanitized measurements.'),('load-validation','Validating harness and documentation','pending','Run local unit and synthetic browser integration tests; document installation, selector calibration, staged workload and limitations.'); INSERT INTO todo_deps(todo_id,depends_on) VALUES('load-validation','load-harness');"
}

Ran terminal command: command -v curl; command -v tar; uname -m; ls /usr/local/bin/node /usr/bin/node /opt/node/bin/node 2>/dev/null; curl -fsS --max-time 20 https://registry.npmjs.org/playwright/latest

Edit , , , , , 

Ran terminal command: curl -fsS --max-time 30 https://nodejs.org/dist/latest-v22.x/SHASUMS256.txt | grep 'linux-x64.tar.xz'

problems
Completed with input: {
  "filePaths": [
    "/home/edg/chatbotIAHub/tests/load/lib.mjs",
    "/home/edg/chatbotIAHub/tests/load/run.mjs"
  ]
}

Edit , , , 

Ran terminal command: mkdir -p /home/edg/.copilot/session-state/5c21e4c6-b013-4aef-8cc1-b5c06c22db3b/files/node-runtime; curl -fsS --max-time 120 https://nodejs.org/dist/v22.23.4/node-v22.23.4-linux-x64.tar.xz -o /home/edg/.copilot/session-state/5c21e4c6-b013-4aef-8cc1-b5c06c22db3b/files/node-runtime/node-v22.23.4-linux-x64.tar.xz; cd /home/edg/.copilot/session-state/5c21e4c6-b013-4aef-8cc1-b5c06c22db3b/files/node-runtime && echo '1805bcd35e6815559bd2eb97db438d3fdb0eb3a5e6a977b7c1badca76337e9ce  node-v22.23.4-linux-x64.tar.xz' | sha256sum --check && tar -xf node-v22.23.4-linux-x64.tar.xz

Ran terminal command: export PATH=/home/edg/.copilot/session-state/5c21e4c6-b013-4aef-8cc1-b5c06c22db3b/files/node-runtime/node-v22.23.4-linux-x64/bin:$PATH; npm install --prefix tests/load; cd tests/load && npx playwright install chromium

runTests
Completed with input: {
  "files": [
    "/home/edg/chatbotIAHub/tests/load/test/config.test.mjs",
    "/home/edg/chatbotIAHub/tests/load/test/browser.test.mjs"
  ]
}
Tool execution failed: No tests found in the files

Ran terminal command: export PATH=/home/edg/.copilot/session-state/5c21e4c6-b013-4aef-8cc1-b5c06c22db3b/files/node-runtime/node-v22.23.4-linux-x64/bin:$PATH; npm test --prefix tests/load

Edit , , 

Ran terminal command: export PATH=/home/edg/.copilot/session-state/5c21e4c6-b013-4aef-8cc1-b5c06c22db3b/files/node-runtime/node-v22.23.4-linux-x64/bin:$PATH; cd tests/load && node --test --test-name-pattern='single login' test/browser.test.mjs

Edit 

Ran terminal command: export PATH=/home/edg/.copilot/session-state/5c21e4c6-b013-4aef-8cc1-b5c06c22db3b/files/node-runtime/node-v22.23.4-linux-x64/bin:$PATH; cd tests/load && node --test --test-name-pattern='single login' test/browser.test.mjs

Edit 

Ran terminal command: export PATH=/home/edg/.copilot/session-state/5c21e4c6-b013-4aef-8cc1-b5c06c22db3b/files/node-runtime/node-v22.23.4-linux-x64/bin:$PATH; npm test --prefix tests/load

The local browser tests now pass for independent logins, popup and iframe launches, synchronized chat rounds, and failure handling. A failed login prevents chat traffic, and an empty or unfinished reply fails the run. I’m finishing the setup guide; the deployed chat selectors will still need a one-user calibration before scaling up.


Edit , , , , , 

Edit , 

Edit , , 

Update harness task status
Completed with input: {
  "description": "Update harness task status",
  "query": "UPDATE todos SET status='done' WHERE id='load-harness'; UPDATE todos SET status='in_progress' WHERE id='load-validation';"
}

Ran terminal command: git --no-pager diff --check; git --no-pager status --short; git --no-pager diff --stat; git check-ignore tests/load/accounts.local.json tests/load/config.local.json tests/load/results/example.json tests/load/node_modules/playwright/package.json

problems
Completed with input: {
  "filePaths": [
    "/home/edg/chatbotIAHub/tests/load"
  ]
}

Ran terminal command: export PATH=/home/edg/.copilot/session-state/5c21e4c6-b013-4aef-8cc1-b5c06c22db3b/files/node-runtime/node-v22.23.4-linux-x64/bin:$PATH; npm ci --prefix tests/load && npm test --prefix tests/load

Read , lines 1 to 250
Completed with input: {
  "path": "/home/edg/chatbotIAHub/tests/load/lib.mjs",
  "view_range": [
    1,
    250
  ]
}

Read 
Completed with input: {
  "path": "/home/edg/chatbotIAHub/tests/load/package-lock.json"
}

Read 
Completed with input: {
  "path": "/home/edg/chatbotIAHub/tests/load/run.mjs"
}

Ran terminal command: git ls-files --others --exclude-standard tests/load; git --no-pager diff --check; rm /home/edg/.copilot/session-state/5c21e4c6-b013-4aef-8cc1-b5c06c22db3b/files/node-runtime/node-v22.23.4-linux-x64.tar.xz

Edit , , , 

Edit 

Added artifact "Automated load testing guide"
Completed with input: {
  "items": [
    {
      "type": "file",
      "label": "Automated load testing guide",
      "isArtifact": true,
      "uri": "file:///home/edg/chatbotIAHub/tests/load/README.md"
    }
  ]
}

problems
Completed with input: {
  "filePaths": [
    "/home/edg/chatbotIAHub/tests/load"
  ]
}

Ran terminal command: export PATH=/home/edg/.copilot/session-state/5c21e4c6-b013-4aef-8cc1-b5c06c22db3b/files/node-runtime/node-v22.23.4-linux-x64/bin:$PATH; npm test --prefix tests/load; git --no-pager diff --check

Complete load harness validation
Completed with input: {
  "description": "Complete load harness validation",
  "query": "UPDATE todos SET status='done', description='Verified npm ci, 14 local unit/browser/CLI tests, report persistence and failure exit status, credential/report ignore rules, editor diagnostics and git diff --check. No real deployment or provider traffic was generated; deployed UI selector calibration remains an operator prerequisite.' WHERE id='load-validation';"
}

I recommend **Playwright for the first version**, since you want real Moodle login and LTI launches—not just API traffic. I’ve added that capability under `tests/load/`, without changing the production deployment.

### What’s included

- Standard Moodle username/password login.
- One isolated browser session per student.
- LTI launch handling for popups, same-tab navigation, and iframes.
- Launch-only tests and synchronized text-chat rounds.
- Explicit `--allow-model-requests` consent before submitting prompts.
- Sanitized JSON reports with outcomes, completion timings, p95 values, and HTTP error counts.
- Failures for empty responses, unfinished generations, visible chat errors, and HTTP 429/5xx responses.

The `setup and testing guide` covers configuration and staged 5 → 15 → 30-user runs.

### Getting started

On a separate load-generator machine with Node.js 22+:

```bash
cd tests/load
npm ci
npx playwright install chromium

cp config.example.json config.local.json
cp accounts.example.json accounts.local.json
chmod 600 config.local.json accounts.local.json
```

Configure the Moodle/tool URLs, distinct student credentials, and chat selectors using the `configuration example`.

**The chat selectors need verification against your deployed UI.** Its source isn’t in this repository, so the harness deliberately rejects placeholder selectors rather than guessing.

Then start small:

```bash
# Validate configuration without network traffic
npm run load -- --users 1 --dry-run

# Real login and LTI launch, without submitting a prompt
npm run load -- --users 1

# One approved model submission
npm run load -- --mode chat --users 1 --rounds 1 --allow-model-requests
```

After calibration, increase to 5, 15, and 30 users, reviewing results between stages.

### Verification and limits

**All 14 local unit, browser, and CLI tests pass**, including report persistence and failure exit codes. No real Moodle or model-provider traffic was generated.

This first version tests **text-chat completion under load**. Image uploads, reconnects, first-token overhead, and server/database monitoring remain separate checks; passing this harness alone does not certify 30-user capacity.