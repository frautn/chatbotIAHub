# Browser load testing

This harness logs into **real Moodle using its standard username/password form**,
opens a configured LTI activity, and waits for the custom Open WebUI through its
public nginx/Gateway route. Each student gets an isolated browser context.
There is no forged LTI token, trusted-header bypass, shared student session, or
saved authentication state.

The first version supports text conversations, popup/same-tab/iframe tools, staggered
launches and synchronized chat rounds. It does not automate image uploads,
forced reconnects, grade verification, or conversation-ownership assertions.
It supplements, not replaces, the [capacity acceptance plan](../../docs/scaling.md).

## Safety and prerequisites

- Use staging or an explicitly approved maintenance window. Real Moodle is now
  part of the end-to-end workload, even though the original sizing report excluded
  Moodle. Its capacity can affect the measurements.
- Run the generator on a **different machine** from the deployment. Monitor that
  machine too: 30-45 browser contexts can themselves become a bottleneck.
- Install Node.js 22+ and npm. No Python dependencies or production Compose
  changes are needed.
- Provision distinct, non-admin synthetic Moodle accounts enrolled in the course
  and allowed to access the chosen activity. Resolve first-login password changes,
  consent screens and onboarding beforehand. SSO/MFA are not supported.
- Select a student activity that pins the intended model. Do not use the shared
  administrator activity. Disable grade forwarding or use a test grade destination.
- Confirm provider quotas and a spend limit outside this harness. Chat mode
  requires `--allow-model-requests`. The harness caps **UI prompt submissions**,
  not provider requests, tokens or cost: functions, retries and tools can add calls.
- Closing a browser on failure does not guarantee cancellation at the provider.
- Use synthetic content only. Credentials and deployment URLs stay in ignored
  local files. Reports contain numeric user IDs, timings, failure categories and
  HTTP status counts, not usernames, passwords, cookies, URLs, prompts or replies.
  Screenshots, traces, HAR files and browser storage are not recorded.

## Install

---
You need Node.js 22. Install using nvm:

https://github.com/nvm-sh/nvm 

I did:

curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.8/install.sh | bash

then:

nvm install 22
---


From the repository root:

```bash
cd tests/load
npm ci
npx playwright install chromium
```

On a Linux machine missing browser system libraries, use
`npx playwright install --with-deps chromium` with permission to install those
system packages. Do not run that command blindly on a shared production host.

```bash
cp config.example.json config.local.json
cp accounts.example.json accounts.local.json
chmod 600 config.local.json accounts.local.json
```

Edit the local files, not the examples:

- `moodleOrigin`: the HTTPS Moodle origin, without a path.
- `activityUrl`: the Moodle activity page, typically
  `https://moodle.example.com/mod/lti/view.php?id=123`. It must belong to that origin.
- `toolOrigin`: the HTTPS **student** tool origin, not an internal container URL.
- `accountsFile`: relative to the configuration file. Supply one unique
  `{ "username": "...", "password": "..." }` entry per simulated user.
- `selectors`: verify against the deployed UI as described below.
- `users`: defaults to 1 in the example; allowed range is 1-45.
- `rounds`: synchronized submissions per user; allowed range is 1-1000.
- `launchIntervalMs`: spacing between login starts; use 1000 for a ramp or 0
  for simultaneous login/launch pressure.
- `thinkMs`: pause between completed chat rounds.
- `timeoutMs`: timeout per browser operation/readiness wait, not an overall run deadline.
- `headless`: set `false` for calibration on a machine with a graphical display.
- `prompt`: a representative synthetic text prompt. The same text is used on each turn.

Keep local filenames as shown so Git ignores them. If you choose alternative
filenames or locations, explicitly exclude them before adding files to Git.

## Calibrate with one student

The custom Open WebUI frontend is an external image, not source in this
repository. Chat selectors intentionally have **no guessed defaults**: the
example is rejected until the placeholders are replaced.

Use browser developer tools to identify stable CSS or Playwright locator selectors:

| Selector | Required meaning |
|---|---|
| `username`, `password`, `login` | Moodle login fields and submit button; examples use standard Moodle IDs |
| `launch` | Activity launch button/link on the Moodle page, or `null` if navigation launches automatically |
| `chatInput` | Unique visible editable message composer in the tool frame |
| `send` | Unique send-message button |
| `busy` | Unique element visible **only during generation**, such as a stop-generation button |
| `assistantMessage` | One element per assistant response containing the response text, in conversation order; exclude user messages and error banners |
| `chatError` | Error banners/failed-generation elements; must not match normal assistant content |

Selectors are strings accepted by Playwright's `locator()`. The tool is discovered
by its expected origin and visible composer, including in an iframe or a new tab.
`launch` is looked up on the Moodle activity page, before entering the tool.
If the activity redirects automatically, keep `launch` as `null`.

First validate files without opening a browser or sending network traffic:

```bash
npm run load -- --users 1 --dry-run
```

Then verify actual login and LTI access, without submitting a prompt:

```bash
npm run load -- --users 1
```

Finally, approve a single model submission to verify generation selectors:

```bash
npm run load -- --mode chat --users 1 --rounds 1 --allow-model-requests
```

The harness arms the busy-element wait before clicking send, requires generation
to start and finish, then requires a newly added, nonempty assistant reply and no
visible chat errors. A missing/misconfigured busy indicator, empty reply, or
timeout is a failure, not a successful stream. Very fast responses whose busy
state cannot be observed may fail conservatively; verify this with the deployed UI
before increasing load. The selectors define this UI-level completion contract;
this is not a protocol-level assertion of an SSE finish event or model correctness.

## Run the workload

Start with launch-only runs at 5, 15, and 30 users:

```bash
npm run load -- --users 5
npm run load -- --users 15
npm run load -- --users 30
```

Check each report and server metrics before proceeding. A new command logs every
student in afresh; it does not reuse stored browser sessions. To stress simultaneous
launches, set `launchIntervalMs` to 0 and repeat after the staggered run passes.

For chat, all students must reach the composer before any prompt is sent. Each
round starts all submissions together and waits for all responses before the next
round. One failed launch prevents the entire cohort from submitting; one failed
chat round prevents further rounds.
Observed HTTP 429 or 5xx responses also prevent subsequent chat rounds (or prevent
chat entirely if observed during launch).

```bash
npm run load -- --mode chat --users 5 --rounds 3 --allow-model-requests
npm run load -- --mode chat --users 15 --rounds 3 --allow-model-requests
npm run load -- --mode chat --users 30 --rounds 3 --allow-model-requests
```

These are separate, operator-reviewed stages, not an automatic escalation.
For a longer soak, increase rounds and choose a realistic `thinkMs` (for example
30000). Duration depends on generation time as well as pauses; this first version
uses bounded rounds rather than a fixed 30-minute scheduler. Thirty users and
30 rounds allow at most 900 UI prompt submissions:

```bash
npm run load -- --mode chat --users 30 --rounds 30 --allow-model-requests --dry-run
# Only after reviewing cost and runtime:
npm run load -- --mode chat --users 30 --rounds 30 --allow-model-requests
```

Only after the 30-user run passes, consider a brief 45-user headroom run.
This first version reuses whichever chat the activity opens/resumes, growing
history over rounds and potentially across runs. Use fresh synthetic identities
or reset test conversations through normal supported administration when comparing
equivalent baselines. Do not compare a fresh conversation with a long resumed one.

## Results and interpretation

Commands print a sanitized plan and write a timestamped JSON report under
`results/` in the current working directory. Run from this directory so the
repository's ignore rules apply. New report directories/files request modes
0700/0600. A normal failed workload still produces a report and exits nonzero.
Startup/configuration/browser-installation/output failures exit nonzero without
claiming a result; raw exceptions are suppressed because Playwright errors can
contain page content and credentials.

Reports include:

- Per-user launch outcome and login-through-composer elapsed time.
- Per-user/per-round chat outcome and send-through-completed-reply elapsed time.
- Nearest-rank p95 for successful launches and completed chats; `null` if none.
- Completed chats, failed journeys, and the maximum planned UI submissions.
- Counts of HTTP responses with status >=400 across all browser contexts.
- A `passed` flag: all planned journeys completed, no context-cleanup failure,
  and no observed HTTP 429 or 5xx responses.

HTTP counts include Moodle, tool and third-party resources. Expected 401/403/404
responses are reported for manual review but do not alone fail a completed
journey. Network failures that do not yield an HTTP response are not included
in these counts; journey timeouts/completion checks still apply.

**`passed` is functional completion under the selected load, not full capacity
certification.** It does not enforce the report's non-generation API p95 or
app-added first-token p95 targets. Chat completion time is not time-to-first-token,
and launch time includes Moodle. Request-level failure rate, precise burst skew,
identity isolation, provider baseline, CPU/memory, restarts, database pools/locks,
and generator saturation need separate measurement.

During each run, monitor the deployment's `docker stats`, Gateway/Open WebUI/nginx
logs, database metrics and provider rate-limit dashboard. Retain the report plus
resource observations and exact image/resource configuration when comparing runs.
Never infer server capacity from the local synthetic fixture tests.

## Test the harness without a deployment

```bash
npm test
```

These tests run only against temporary local HTTP fixtures and Chromium, with no
real Moodle, LTI platform or model API calls. They check configuration, CLI spend
consent, independent logins, popup/iframe discovery, synchronized rounds, empty
responses, timeout behavior, context cleanup and sanitized output. The fixtures
simulate the redirect/UI boundary; they do not validate LTI signatures. Keep the
existing [Gateway functional suite](../../gateway/README.md#development) for that.
