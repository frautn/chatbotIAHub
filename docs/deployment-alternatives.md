# Deployment plan & cost comparison — Chatbot IA Hub (300 users / 30 concurrent)
2026 Nov 24

## 1. What's actually being deployed

From the repo, three Docker Compose stacks run on one Ubuntu host (`docker/docker-compose-lti.yml`, `docker-compose-openwebui.yml`, `docker-compose-postgres.yml`):

- **LTI gateway** (Flask/gunicorn, CPU-only, trivial resource footprint) — handles LTI 1.1/1.3 launches, SSO, chat resuming, grade sync.
- **Open WebUI** ×2 (stock admin + LTI student instance) — the chat UI, CPU-only itself; it calls an **external, OpenAI-compatible LLM endpoint** via `OPENAI_API_BASE_URL`/`OPENAI_API_KEY` (`.env.example` defaults to Google's Gemini endpoint today).
- **Postgres** — Open WebUI's metadata/chat DB (small; images are not stored in Postgres, they live on the `openwebui-shared-data` volume on local disk).
- **nginx** in front of everything.

Important consequence: **no GPU is needed to run the Ubuntu host itself.** The "Cloud GPU vs paid API" question is entirely about what you point `OPENAI_API_BASE_URL` at — a hosted vision API, or your own vLLM/Ollama server running on a rented GPU.

## 2. Usage assumptions (please sanity-check these — everything below scales off them)

| Assumption | Value |
|---|---|
| Total students | 300 |
| Concurrent peak | 30 |
| Turns/conversation | min 2, avg 2.5, capped (e.g. 6–8) |
| Images/turn | ~1.5 avg |
| System/rubric prompt per activity | ~3,000 tokens (your `prompt XML files` run ~11–12 KB ≈ 3,000+ tokens each) |
| Image cost | ~1,000–1,100 tokens/image (typical vision-API tiling of a full phone photo) |
| Model output | ~500 tokens/turn |
| → Per conversation (2.5 turns) | **~16,000 input + ~1,300 output tokens** (rough planning number; refine with real usage once live — Open WebUI's admin panel and your own `load-test harness` can both be extended to log this) |
| Conversations/cycle | 300 (one problem set, all students) |

Everything scales linearly if you run multiple problem sets per term — I give 1×/4×/8× cycles below.

## 3. Ubuntu host (gateway + Open WebUI + Postgres)

This is CPU/RAM/disk sizing, not GPU. Workload is bursty HTTP/SSE for ≤30 concurrent sessions — not heavy.

| Tier | Spec | Indicative cost (e.g. Hetzner Cloud, Nov 2026 list prices) |
|---|---|---|
| Minimum viable | 2–4 vCPU / 4–8 GB RAM, shared | ~€5.50–20/mo |
| Recommended | 4 vCPU / 8 GB RAM, dedicated vCPU | ~€37–45/mo |
| Comfortable headroom (both WebUI instances + Postgres + growth) | 8 vCPU / 16 GB RAM, dedicated vCPU | ~€55–70/mo |

Any mainstream VPS provider (Hetzner, OVH, DigitalOcean, Contabo) in this size class is fine; nothing here is provider-specific. Add automated `pg_dump` backups (cheap, CPU-light) and keep nginx/TLS as already documented in `gateway/README.md`.

## 4. Image storage

Phone photos of handwritten work aren't auto-compressed by this stack, so plan for ~1–3 MB/image.

| Cycle volume | Images (300 users × 2.5 turns × 1.5 img) | Storage/cycle (avg 1.5 MB) |
|---|---|---|
| 1 cycle | ~1,125 | ~1.7 GB |
| 4 cycles/term | ~4,500 | ~6.8 GB |
| 8 cycles/term | ~9,000 | ~13.5 GB |

This is cheap either way: a 50–100 GB block volume on the same VPS (~$3–7/mo) covers a full term with headroom. If you outgrow local disk or want offsite durability, Open WebUI can be pointed at S3-compatible object storage (e.g., Hetzner Object Storage, Backblaze B2 ≈ $6/TB/mo) instead of the local volume — worth doing once you're keeping multiple terms of history, not needed at day one.

## 5. LLM inference: hosted API vs self-hosted GPU

**Key framing:** there is no actually-free GPU for production, 30-concurrent-user serving. "Free models" (Qwen-VL, Llama-Vision, InternVL, etc.) are free *weights*; RunPod/HuggingFace still bill you per GPU-hour to run them. HF's free tiers (ZeroGPU, free Spaces) are shared/queued and not meant for guaranteed concurrent production load.

### 5a. Hosted vision APIs

| Provider/model | Standard price | Batch/async price | Notes |
|---|---|---|---|
| **Gemini 3.8 Flash** (already the project's default) | $0.75/M in, $3.75/M out | $0.375/M in, $1.875/M out (50% off, async) | Has a free tier, but free-tier content **is used to improve Google's products** — likely unacceptable for student work; use paid tier |
| **Moonshot/Kimi K3.1 Pro** (vision-capable flagship, per `docs/privacy.md`'s no-training policy) | $2/M in, $10/M out | $1.20/M in, $6/M out (40% off, async, 24h-ish turnaround) | Direct Moonshot AI pricing; never trains on your data even on the standard tier |

Monthly cost at the per-conversation estimate (~16K in / ~1.3K out tokens):

| Cycles/month | Gemini standard | Gemini batch | Moonshot standard | Moonshot batch |
|---|---|---|---|---|
| 1 (300 convos) | ~$5 | ~$2.5 | ~$13.5 | ~$8 |
| 4 (1,200 convos) | ~$20 | ~$10 | ~$54 | ~$32 |
| 8 (2,400 convos) | ~$41 | ~$20 | ~$108 | ~$65 |

**At this scale, LLM inference is a rounding error compared to the VPS, no matter which paid API you choose.** Moonshot costs more per token than Gemini Flash but buys an explicit no-training guarantee from day one.

### 5b. Self-hosted open-weight VLM on rented GPU

A vision-capable 7B–32B open model (Qwen2.5/3-VL class, InternVL, Llama-Vision — benchmark on your actual rubric-grading task before committing) via vLLM/Ollama.

| Mode | GPU | Cost | Fit for 30 concurrent |
|---|---|---|---|
| Always-on pod (RunPod L40S 48GB, Secure Cloud) | $1.09/hr | **~$795/mo** | Overkill — pays 24/7 for a few hours/day of real traffic |
| Always-on pod (RunPod A100 80GB) | $2.09–2.19/hr | **~$1,525–1,600/mo** | Same issue, bigger model headroom |
| HF Spaces dedicated GPU (1×L40S) | $1.80/hr | **~$1,296/mo** flat | Same always-on problem |
| **Serverless, scale-to-zero + batching** (RunPod Serverless, 48GB tier) | ~$1.89/hr, billed per second only while active | **roughly $20–50/mo**, dominated by cold-start seconds, not compute | Plausible, but see caveat below |

The serverless+batch number is genuinely uncertain without a pilot — it depends on cold-start time (model load) vs how large a batch window you accumulate before triggering a run. Validate with a small RunPod trial before budgeting it as fact.

**Bottom line:** self-hosting only gets cost-competitive with the hosted APIs if you build the scale-to-zero batching infrastructure described below — and even then the GPU dollars saved vs. e.g. Gemini's Batch API (~$10–20/mo at your volume) are marginal. The case for self-hosting is really about **data control/compliance**, not raw savings, at 300 users.

## 6. The "delay/batch replies to save GPU time" idea — two different implementations

This single idea maps to two very different amounts of engineering work depending on which backend you pick:

**Path A — hosted API + provider Batch API (low effort).** Gemini and Moonshot both offer an async Batch endpoint at ~40–50% discount, with results back in minutes to ~24h. You'd submit the student's turn as a batch job instead of an inline chat completion, poll for completion, then push the reply back into the same Open WebUI chat. The gateway already has the needed building block: `webui_client.py` already signs in to Open WebUI on a learner's behalf, and `/api/scores` in `gateway/README.md` already shows the pattern of a trusted backend writing results back asynchronously. Extending that pattern to post a delayed assistant message is a modest addition, not a new subsystem. UX-wise you'd show students a "tu tutor está revisando tu entrega" placeholder.

**Path B — self-hosted GPU + custom batch orchestration (high effort).** You'd need: a queue (Redis/RQ or similar) to accumulate pending turns, logic to trigger a RunPod/HF pod start once N requests are queued or T minutes elapse, a vLLM server to actually batch the accumulated requests together, and the same "write the reply back into Open WebUI" step as Path A. This is real new infrastructure to build and operate (retries, failure handling, monitoring, cold-start tuning), on top of running the model server itself.

Given your volume, **Path A gets you the exact behavior you described (batched, delayed, cheaper replies) for a fraction of the engineering cost**, and works today regardless of which hosted API you pick.

## 7. Recommended phased approach

1. **Start with the hosted-API path, unchanged architecture.** Keep `OPENAI_API_BASE_URL` pointed at Gemini's paid tier (already the default) or switch to Moonshot if the no-training guarantee is a hard requirement. Cost: VPS (~€40–70/mo) + a few to a few dozen dollars/month in inference — trivial at 300 users.
2. **If/when you want delayed responses to save cost (or to decouple grading from class time), implement Path A** (provider Batch API + a small write-back extension to the gateway). Cheap to build, cheap to run, ~40–50% further inference savings.
3. **Only invest in self-hosted GPU (Path B) if** a privacy/compliance requirement forces on-prem/self-hosted inference, or volume grows by 10–50× such that GPU-hour costs genuinely undercut API costs — and even then, pilot the serverless+batching cold-start numbers with your own `load-test harness` before committing budget, since those numbers are the least certain part of this whole estimate.

Let me know if you'd like me to turn any part of this into an actual implementation task (e.g., wiring up a Batch API flow, or sizing a specific self-hosted model), or if you want the assumptions (turns, images/turn, cycles/term) adjusted and the tables recomputed.

# ASYNC alternatives

Open WebUI has no concept of an asynchronous/batch completion backend. Every model call — whether through its built-in OpenAI-compatible connector (`OPENAI_API_BASE_URL`) or a custom "Pipe" function — happens **inside one live HTTP (and usually websocket) request** that the browser is actively waiting on. The `pipe()` coroutine must return (or finish streaming) within that request's lifetime; there's no "submit now, deliver the real answer in 10 minutes" primitive anywhere in the chat pipeline.

That matters here because Gemini's and Moonshot's Batch APIs are a **structurally different API surface**, not a slower version of `/chat/completions`:

- **Gemini Batch**: `client.batches.create(model=..., src=<inline requests or a JSONL file>)` → returns a job resource you poll; target turnaround "24 hours, often quicker."
- **Moonshot Batch**: a separate `BatchJob` resource with its own `completion_window`; "processed asynchronously and concurrently... tasks must complete within the specified completion_window or they expire."

You can't just point `OPENAI_API_BASE_URL` at either of these — nothing in Open WebUI speaks that job-submit/poll/fetch-results protocol.

## What Open WebUI *does* give you to bridge the gap

This repo already uses the two relevant extension points, in `docker/openwebui-functions/`:

- **Pipe functions** — register as a custom "model." Inside the live request, `pipe()` can return a string immediately, or stream via a generator, but it's still bounded by the request (nginx/gunicorn/browser timeouts — think tens of seconds to a couple of minutes, not hours).
- **Filters with direct chat access** — `change-chat-title.py` already shows the pattern of reaching into `open_webui.models.chats.Chats` to read/mutate a chat's stored message tree and push a live update via `__event_emitter__`. `pass-grade-to-gateway.py` shows the companion pattern: a Filter calling *out* to the gateway's API.

Neither of these lets a request stay open for a 24h-SLA batch job — but together they're exactly the building blocks for a two-phase design:

## The two-phase design this implies

**Phase 1 — inside the live request (a Pipe function, fast):**
The student's turn (text + images) hits a Pipe function acting as the pinned model. It stages the request (e.g., appends it to a small outbox table/queue) and returns immediately with an acknowledgment, e.g. *"Recibimos tu entrega; vas a ver la corrección acá la próxima vez que entres."* This satisfies Open WebUI's synchronous request/response contract — no code change to Open WebUI itself, just a new Function.

**Phase 2 — outside any live request (a standalone worker, slow):**
A separate process (could live alongside the gateway) periodically:
1. Packages accumulated outbox entries into one Gemini `batches.create(...)` or Moonshot `BatchJob` call.
2. Polls until the job completes (minutes, occasionally up to the provider's SLA window).
3. Writes each graded reply back into the *right* chat. Since there's no documented "append one message" REST endpoint, the realistic approach — already proven by this repo's own `change-chat-title.py` — is to sign in via Open WebUI's trusted-header flow (exactly what `webui_client.py` already does for chat-resuming) and patch the chat's message tree directly, optionally also firing `__event_emitter__` if the student still has the tab open — but the DB write is what guarantees they see it later, since a socket push is useless once the tab is closed.

This is also why this project's architecture is unusually well-suited to that delay: the **existing "resume conversation" mechanism** (`GATEWAY_WEBUI_INTERNAL_URL`, documented in `gateway/README.md`) already drops a returning student back into the *same* `chat_id` on their next Moodle launch. "Submit now, come back later to see it" maps naturally onto "relaunch the LTI activity later," with no separate notification channel strictly required (though email/Moodle messaging could be added for a nicer UX).

## What this costs you in practice

This is **genuinely new code, not a config flip**: a new Pipe function (stage + ack), a new worker (submit/poll per-provider — Gemini's and Moonshot's batch shapes aren't interchangeable, so you'd write provider-specific adapters), and write-back logic against Open WebUI's internal chat storage (undocumented shape, reached the same way the existing Filter already does — reasonable here since you're running a forked image anyway, but worth knowing it's not a stable public contract). It's much smaller than Path B (self-hosted GPU + vLLM + scheduler) from the earlier comparison, but it's not free.

Given the dollar savings at your volume were modest (~$10–20/month from the Batch API discount alone), it's worth asking whether that's worth building versus two lighter alternatives:
- **Do nothing** — just eat the (already tiny) standard per-request cost.
- **"Soft" delay without a real Batch API** — have the Pipe function queue and rate-limit calls to the *normal* synchronous endpoint on a timer (e.g., drain the queue every few minutes), smoothing bursts without ever leaving the standard API shape or touching the 24h-SLA batch surface. No provider discount, but far less integration risk, and it still keeps the "live chat, just a bit slower" UX instead of "come back later."


# Which LLM?
2026 Nov 24

Let's compare LLMs performance. I don't think using the most expensive models is important here. I tested Kimi 2.6 and it worked fine. We have to consider that the system prompt holds a lot of information, including examples and solutions, and there is little room for the LLM to create new content. The most important aspects of the LLM are: reading handwritten images of physics problems solutions, and following instructions strictly. Could you recommend different LLMs for this?


## Framing: this is a different axis than "smartest/most expensive"

For this task, raw frontier reasoning isn't the bottleneck — you said it yourself: the system prompt already carries the rubric, examples and worked solutions, so the model mostly needs to (1) **read messy handwritten math/physics off a phone photo accurately**, and (2) **stay inside the lines** of a long, prescriptive instruction set instead of improvising. Those are two fairly distinct, well-studied capabilities, and the ranking of "best overall chatbot" doesn't track either of them well. So I'll evaluate candidates on those two axes specifically, not on general leaderboard position.

## One thing to flag before the comparison: Kimi K2.6

I checked Moonshot's own current model list. **`kimi-k2.6` is deprecated on Moonshot's first‑party API** — "No longer available to newly registered users... Deprecation expected in late December 2026" — and it isn't listed in Moonshot's "Multi-modal Model" table at all; only `kimi-k3`, `kimi-k3.1-pro` and `kimi-k3.1-pro-highspeed` are listed there as having "native visual understanding." K2.6 is still servable because it's open-weight and third-party hosts (DeepInfra, Chutes, etc., ~$0.4–1.1/M in, $1.8–5.25/M out) keep running it, but if you tested it **directly against Moonshot's API**, it's worth double-checking:
- whether you actually sent it raw images (vs. already-transcribed text), and
- whether you want to keep depending on Moonshot's own endpoint for it, since they're sunsetting it there.

If it was genuinely reading photos and grading well, that's a good, cheap data point — just plan to move to `kimi-k3` or `kimi-k3.1-pro` (or a third-party K2.6 host) rather than assume Moonshot's own K2.6 endpoint stays available.

## Shortlist for OCR-of-handwriting + strict instruction-following

| Model | Price (in/out per M tok) | Handwriting/OCR fit | Instruction-adherence fit | Self-hostable later? |
|---|---|---|---|---|
| **Qwen3-VL-30B-A3B-Instruct** (hosted via DeepInfra/SiliconFlow) | $0.15 / $0.60 | Qwen's VL line (2.5-VL, 3-VL) is consistently at or near the top of open-weight OCR/document benchmarks (OCRBench, DocVQA-style tasks) across many languages, including messy/real-world handwriting — this is its specific strength | Solid; Qwen is heavily RLHF'd for structured/constrained output, though not as famously "literal" as Claude | **Yes** — same open weights run locally (RunPod/HF) without re-validating a different model later; larger variants (e.g. 235B-A22B) exist if you need more headroom |
| **Gemini 2.5/3.8 Flash** (already your default) | $0.75 / $3.75 | Google's OCR/document-AI heritage gives it a strong, broad reputation on photographed real-world text and diagrams | Good; long context handles your large rubric+examples cheaply, and it already works in this stack with zero migration | No (closed) |
| **Kimi K3 / K3.1-Pro** (Moonshot direct, the *current* vision models) | K3.1-Pro: $2 / $10 | Less specifically benchmarked on handwriting than Qwen/Gemini; general vision is competent but not its headline strength | Strong — Moonshot tunes heavily for long, structured, agentic instruction-following | K3 is open-weight (could self-host a huge MoE, impractical at your scale); K3.1-Pro is closed |
| **Claude Haiku 4.5** | $1 / $5 | Decent, but not typically cited as a handwriting/OCR specialist the way Qwen/Gemini are | **Anthropic models are the most commonly cited for literal, non-embellishing instruction-following** — exactly your "little room to create new content" requirement | No (closed) |
| **GPT-5-mini** | $0.25 / $2 (even cheaper on a "flex" tier, ~$0.125/$1) | Competent generalist vision, not a specialist in either direction | Solid, no particular edge | No (closed) |

Caveat on this table: price/deprecation/modality claims are verified from vendor docs today; the **OCR and instruction-following comparisons are reputational/benchmark-based**, not something I've run against your actual rubric+handwriting data. Given handwriting legibility, Spanish-language math notation, and your specific rubric phrasing all matter a lot here, I'd treat this table as a shortlist to test, not a final verdict.

## Recommendation

1. **Qwen3-VL (30B-A3B to start) as the primary candidate to try next.** It's the cheapest option here by a wide margin, has the best-documented track record specifically on OCR/handwriting-style tasks, and — unlike every other option in the table — the exact same weights are something you could self-host later without re-validating a different model, which keeps your earlier GPU-vs-API comparison open as a real future option rather than a hypothetical.
2. **Keep Gemini Flash as your safe baseline** — zero migration cost since it's already wired in, and it's priced close to Qwen3-VL.
3. **Use Claude Haiku as a targeted fallback, not a first pick** — reach for it specifically if you observe the current model embellishing, hallucinating extra steps, or drifting from the rubric; that's precisely the failure mode it's reputed to resist best, even though it's pricier and less OCR-specialized.
4. **Treat Kimi K3.1-Pro as the "same family, now-supported" option** if you liked K2.6's behavior and want to stay with Moonshot — same vendor, but accept it's 2–10× the per-token cost of Qwen3-VL/Gemini Flash.

## Suggested way to actually decide

Given you already found empirical testing more convincing than spec sheets (that's how you found K2.6 "worked fine"), the cheapest way to settle this is a small side-by-side: reuse a handful of real images from `data/problemas/` and a rubric from `data/prompts/`, send the same system prompt + image to 3–4 shortlisted models, and have a human (you) score the outputs against the rubric for both reading accuracy and instruction compliance. I can help script that comparison (a small standalone script, not touching the running deployment) if useful — want me to put that together?