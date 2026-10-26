I’ll inspect the deployment configuration, Gateway concurrency behavior, and this machine’s resources, then recommend OCI sizing and a way to validate 30 simultaneous users. I’ll leave Moodle out of scope and won’t change the running services.


Read 
Completed with input: {
  "path": "/home/ubuntu/chatbotIAHub/docker/docker-compose-openwebui.yml"
}

Read 
Completed with input: {
  "path": "/home/ubuntu/chatbotIAHub/docker/docker-compose-lti.yml"
}

Read 
Completed with input: {
  "path": "/home/ubuntu/chatbotIAHub/docker/docker-compose-postgres.yml"
}

Read , lines 1 to 220
Completed with input: {
  "path": "/home/ubuntu/chatbotIAHub/gateway/README.md",
  "view_range": [
    1,
    220
  ]
}

Ran terminal command: git --no-pager status --short; printf '\nHost resources\n'; lscpu | grep -E 'Architecture|CPU\(s\)|Model name|Thread|Core|Socket'; free -h; df -h / /home/ubuntu/chatbotIAHub; printf '\nContainer overview\n'; docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'; printf '\nContainer resource usage\n'; docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.PIDs}}'

Find files matching `gateway/lti_gateway/**/*.py`

Read 
Completed with input: {
  "path": "/home/ubuntu/chatbotIAHub/gateway/Dockerfile"
}

Read , lines 1 to 260
Completed with input: {
  "path": "/home/ubuntu/chatbotIAHub/gateway/lti_gateway/store.py",
  "view_range": [
    1,
    260
  ]
}

Read , lines 1 to 260
Completed with input: {
  "path": "/home/ubuntu/chatbotIAHub/gateway/lti_gateway/webui_client.py",
  "view_range": [
    1,
    260
  ]
}

Read , lines 1 to 260
Completed with input: {
  "path": "/home/ubuntu/chatbotIAHub/docker/nginx-lti1.retag.lat.conf",
  "view_range": [
    1,
    260
  ]
}

Read 
Completed with input: {
  "path": "/home/ubuntu/chatbotIAHub/docker/nginx-owui.retag.lat.conf"
}

Search for `requests\.|sqlite|timeout|Store|cache|auth_request|async|thread|Semaphore`

Find files matching `docker/openwebui-functions/*`

Read , lines 1 to 250
Completed with input: {
  "path": "/home/ubuntu/chatbotIAHub/gateway/lti_gateway/app.py",
  "view_range": [
    1,
    250
  ]
}

Read , lines 1 to 200
Completed with input: {
  "path": "/home/ubuntu/chatbotIAHub/gateway/lti_gateway/config.py",
  "view_range": [
    1,
    200
  ]
}

Read , lines 1 to 260
Completed with input: {
  "path": "/home/ubuntu/chatbotIAHub/docker/openwebui-functions/pass-grade-to-gateway.py",
  "view_range": [
    1,
    260
  ]
}

Read , lines 1 to 220
Completed with input: {
  "path": "/home/ubuntu/chatbotIAHub/docker/openwebui-functions/change-chat-title.py",
  "view_range": [
    1,
    220
  ]
}

Read 
Completed with input: {
  "path": "/home/ubuntu/chatbotIAHub/docker/backup-openwebui.sh"
}

"Fetch Web Content" failed
Completed with input: {"url":"https://docs.openwebui.com/tutorials/deployment/scaling/"}
Tool execution failed: Error: Failed to fetch https://docs.openwebui.com/tutorials/deployment/scaling/ - status code 404

Fetched [https://docs.oracle.com/en-us/iaas/Content/Compute/References/computeshapes.htm](https://docs.oracle.com/en-us/iaas/Content/Compute/References/computeshapes.htm)
Completed with input: {"url":"https://docs.oracle.com/en-us/iaas/Content/Compute/References/computeshapes.htm"}

Ran terminal command: printf 'OCI shape (non-sensitive fields only)\n'; curl --noproxy '*' --connect-timeout 2 --max-time 4 -fsS -H 'Authorization: Bearer Oracle' http://169.254.169.254/opc/v2/instance/ | python3 -c 'import sys,json; d=json.load(sys.stdin); print(json.dumps({k:d[k] for k in ("shape","shapeConfig","region") if k in d},indent=2))'; printf '\nSelected runtime settings and mounts\n'; python3 - <<'PY'
import json,subprocess
keys={'UVICORN_WORKERS','DATABASE_POOL_SIZE','DATABASE_POOL_MAX_OVERFLOW','DATABASE_POOL_TIMEOUT','DATABASE_POOL_RECYCLE','DATABASE_ENABLE_SESSION_SHARING','REDIS_URL','WEBSOCKET_MANAGER','WEBSOCKET_REDIS_URL','ENABLE_WEBSOCKET_SUPPORT','VECTOR_DB','CHROMA_HTTP_HOST','QDRANT_URI','ENABLE_OLLAMA_API','ENABLE_RAG_WEB_SEARCH','ENABLE_RAG_LOCAL_WEB_FETCH','ENABLE_TITLE_GENERATION','ENABLE_FOLLOW_UP_GENERATION','ENABLE_TAGS_GENERATION'}
for name in ['openwebui-for-moodle','openwebui-lti','lti-gateway','lti11-gateway']:
 d=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
 print(name,'CMD=',d['Config']['Cmd'],'MemoryLimit=',d['HostConfig']['Memory'],'NanoCpus=',d['HostConfig']['NanoCpus'])
 print('Mounts:',[(m['Type'],m['Destination'],m.get('Name','')) for m in d['Mounts']])
 for entry in d['Config']['Env']:
  k,_,v=entry.partition('=')
  if k in keys:
   print(k,'=', '<configured>' if any(x in k for x in ['URL','URI','HOST']) else v)
PY
printf '\nHost nginx concurrency and active upstream settings\n'; grep -R -nE 'worker_processes|worker_connections|worker_rlimit_nofile|auth_request |proxy_pass |proxy_(read|send)_timeout|proxy_buffering|server_name' /etc/nginx/nginx.conf /etc/nginx/sites-enabled 2>/dev/null | head -100

"Fetch Web Content" failed
Completed with input: {"url":"https://docs.openwebui.com/tutorials/scaling/"}
Tool execution failed: Error: Failed to fetch https://docs.openwebui.com/tutorials/scaling/ - status code 404

"Fetch Web Content" failed
Completed with input: {
  "url": "https://docs.openwebui.com/getting-started/env-configuration/",
  "max_length": 4000
}
Tool execution failed: Error: Failed to fetch https://docs.openwebui.com/getting-started/env-configuration/ - status code 404

Fetched [https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Fre...](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
Completed with input: {"url":"https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm"}

Fetched [https://ai.google.dev/gemini-api/docs/rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits)
Completed with input: {"url":"https://ai.google.dev/gemini-api/docs/rate-limits"}

Read , lines 240 to 300
Completed with input: {
  "path": "/home/ubuntu/chatbotIAHub/gateway/lti_gateway/app.py",
  "view_range": [
    240,
    300
  ]
}

Read , lines 1 to 120
Completed with input: {
  "path": "/home/ubuntu/chatbotIAHub/docker/backup-openwebui.sh",
  "view_range": [
    1,
    120
  ]
}

Ran terminal command: printf 'PostgreSQL capacity and aggregate activity\n'; docker exec pgsql-moodlewebui sh -c 'psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off -c "SELECT name,setting,unit FROM pg_settings WHERE name IN ('\''max_connections'\'','\''shared_buffers'\'','\''effective_cache_size'\'','\''work_mem'\'','\''maintenance_work_mem'\'','\''wal_level'\''); SELECT count(*) AS total_connections, count(*) FILTER (WHERE state='\''active'\'') AS active, count(*) FILTER (WHERE wait_event_type='\''Lock'\'') AS waiting_on_lock FROM pg_stat_activity; SELECT pg_size_pretty(pg_database_size(current_database())) AS database_size; SELECT datname,numbackends,xact_commit,xact_rollback,deadlocks,temp_bytes FROM pg_stat_database WHERE datname=current_database();"'; printf '\nRunning Open WebUI startup and concurrency defaults\n'; docker exec openwebui-lti sh -c 'grep -nE "UVICORN_WORKERS|uvicorn|WEBUI_WORKERS" /app/backend/start.sh; grep -nE "DATABASE_POOL|SESSION_SHARING|pool_size|max_overflow|create_engine|create_async_engine" /app/backend/open_webui/internal/db.py; grep -nE "UVICORN_WORKERS|DATABASE_POOL|WEBSOCKET_MANAGER|WEBSOCKET_REDIS|VECTOR_DB|CHROMA_HTTP_HOST|REDIS_URL" /app/backend/open_webui/env.py /app/backend/open_webui/config.py /app/backend/open_webui/socket/main.py | head -100'; printf '\nVolume sizes (no file contents)\n'; docker system df -v --format '{{json .}}' 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get("Volumes", []),indent=2))'

Read tool output
Completed with input: {
  "path": "/tmp/1793050449266-copilot-tool-output-119353-1478364c-b4b2-4e99-8639-8c23e229e2ed.txt",
  "view_range": [
    1,
    130
  ]
}

Search for `VM.Standard.A1.Flex|OCPU|core|thread`

Search for `per minute|RPM|TPM|RPD|project|tier|capacity`

Fetched [https://docs.openwebui.com/](https://docs.openwebui.com/)
Completed with input: {"url":"https://docs.openwebui.com/"}

Ran terminal command: printf 'Official Open WebUI documentation URLs for deployment and scaling\n'; curl --connect-timeout 5 --max-time 20 -fsSL https://docs.openwebui.com/sitemap.xml | python3 -c 'import sys,xml.etree.ElementTree as E; r=E.fromstring(sys.stdin.read()); print("\n".join(e.text for e in r.iter() if e.tag.endswith("loc") and any(x in e.text.lower() for x in ("scal","env","redis","deploy","vector","storage"))))'

The machine is an A1 Flex with 2 OCPUs and 12 GB RAM, with plenty of available memory in this idle snapshot. The more immediate concerns are disk space—only 9.5 GB remains—and the Gateway’s two synchronous workers. I’m checking the model-provider configuration and Open WebUI’s scaling requirements so the recommendation addresses those bottlenecks, not just VM size.
The VM is an Ampere A1 with 2 OCPUs and 12 GB RAM. It has plenty of available memory in this snapshot, but disk space is tighter. The main concurrency risk I found is the Gateway: it has two synchronous workers, handles authentication checks for the custom UI, and can occupy those workers with chat-resume lookups. I’m checking Open WebUI’s scaling requirements before recommending a single-VM or multi-VM layout.


Fetched [https://docs.openwebui.com/getting-started/advanced-topics/scaling](https://docs.openwebui.com/getting-started/advanced-topics/scaling)
Completed with input: {"url":"https://docs.openwebui.com/getting-started/advanced-topics/scaling/"}

Fetched [https://docs.openwebui.com/reference/env-configuration](https://docs.openwebui.com/reference/env-configuration)
Completed with input: {"url":"https://docs.openwebui.com/reference/env-configuration/"}

Fetched [https://www.oracle.com/cloud/compute/arm/pricing/](https://www.oracle.com/cloud/compute/arm/pricing/)
Completed with input: {"url":"https://www.oracle.com/cloud/price-list/#pricing-compute"}

Read , lines 310 to 340
Completed with input: {
  "path": "/home/ubuntu/chatbotIAHub/gateway/lti_gateway/app.py",
  "view_range": [
    310,
    340
  ]
}

Ran terminal command: printf 'Open WebUI effective provider family and persisted feature switches (no credentials)\n'; docker exec -i openwebui-lti python - <<'PY'
import os,json
from urllib.parse import urlsplit
import psycopg2
u=os.environ['DATABASE_URL'].replace('postgresql+psycopg2://','postgresql://').replace('postgresql+psycopg://','postgresql://')
with psycopg2.connect(u) as conn:
 conn.set_session(readonly=True)
 with conn.cursor() as cur:
  cur.execute('SELECT data FROM config ORDER BY id DESC LIMIT 1')
  row=cur.fetchone()
  data=row[0] if row else {}
  if isinstance(data,str): data=json.loads(data)
  paths=['openai.api_base_urls','ollama.enable','task.enable_title_generation','task.enable_tags_generation','task.enable_follow_up_generation','rag.embedding_engine','rag.web.search.enable','storage.provider']
  for path in paths:
   v=data
   for k in path.split('.'):
    v=v.get(k) if isinstance(v,dict) else None
   if path=='openai.api_base_urls' and v:
    v=[urlsplit(x).hostname for x in v]
   print(path, '=', v if v is not None else '<not persisted>')
PY
printf '\nInstalled WebUI storage defaults and filter execution\n'; docker exec openwebui-lti sh -c 'grep -nE "USE_SLIM|STORAGE_PROVIDER|ENABLE_WEBSOCKET_SUPPORT" /app/backend/open_webui/env.py /app/backend/open_webui/config.py | head -24; grep -nE "is_coroutine|iscoroutine|to_thread|run_in_threadpool|filter_function|filter_handler" /app/backend/open_webui/utils/filter.py | head -35'; printf '\nWebUI DB engine construction\n'; docker exec openwebui-lti sh -c 'sed -n "402,423p" /app/backend/open_webui/internal/db.py; sed -n "478,502p" /app/backend/open_webui/internal/db.py'; printf '\nBasic service readiness (non-authenticated GETs only)\n'; for port in 3000 3001 8090 8091; do if [ "$port" -lt 8000 ]; then route=/health; else route=/healthz; fi; curl --noproxy '*' --connect-timeout 2 --max-time 5 -sS -o /dev/null -w "port $port: HTTP %{http_code}, %{time_total}s\n" "http://127.0.0.1:$port$route"; done

Search for `Redis|UVICORN_WORKERS|WEBSOCKET|DATABASE_POOL|S3|Chroma|sticky|affinity|singl...`

Ran terminal command: printf 'Current config schema and synchronous filter dispatch\n'; docker exec openwebui-lti sh -c 'sed -n "150,166p" /app/backend/open_webui/utils/filter.py; grep -nE "class Config|__tablename__|Mapped|Column|key|value" /app/backend/open_webui/models/configs.py | head -45'; printf '\nConfig column names only\n'; docker exec pgsql-moodlewebui sh -c 'psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "SELECT column_name,data_type FROM information_schema.columns WHERE table_name='\''config'\'' ORDER BY ordinal_position;"'; printf '\nSelected runtime provider and storage families\n'; python3 - <<'PY'
import subprocess,json
from urllib.parse import urlsplit
for name in ['openwebui-for-moodle','openwebui-lti']:
 d=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
 env=dict(e.split('=',1) for e in d['Config']['Env'])
 print(name)
 for k in ['OPENAI_API_BASE_URL','DATABASE_URL']:
  u=urlsplit(env.get(k,'')); print(k, {'scheme':u.scheme,'hostname':u.hostname,'database':u.path if k=='DATABASE_URL' else '<omitted>'})
 for k in ['USE_SLIM_DOCKER','VECTOR_DB','STORAGE_PROVIDER','UVICORN_WORKERS']:
  print(k, env.get(k,'<image default>'))
PY

Read , lines 55 to 128
Completed with input: {
  "path": "/tmp/1793050518821-copilot-tool-output-6d51690e81734ecc8d9affdd14767df4.txt",
  "view_range": [
    55,
    128
  ]
}

Fetched [https://platform.moonshot.ai/docs/pricing/limits](https://platform.moonshot.ai/docs/pricing/limits)
Completed with input: {"url":"https://platform.kimi.ai/docs/pricing/limits"}

Ran terminal command: printf 'Persisted provider hosts and selected feature flags\n'; docker exec -i openwebui-lti python - <<'PY'
import os,json
from urllib.parse import urlsplit
import psycopg2
keys=['openai.api_base_urls','ollama.enable','task.enable_title_generation','task.enable_tags_generation','task.enable_follow_up_generation','rag.embedding_engine','rag.web.search.enable','storage.provider']
with psycopg2.connect(os.environ['DATABASE_URL']) as conn:
 conn.set_session(readonly=True)
 with conn.cursor() as cur:
  cur.execute('SELECT key,value FROM config WHERE key=ANY(%s)',(keys,))
  rows=dict(cur.fetchall())
for key in keys:
 v=rows.get(key)
 if key=='openai.api_base_urls' and v:
  if isinstance(v,str): v=json.loads(v)
  v=[urlsplit(url).hostname for url in v]
 print(key,'=',v if v is not None else '<not persisted>')
PY
printf '\nRegistered function counts and known function enablement (no source or valves)\n'; docker exec pgsql-moodlewebui sh -c 'psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off -c "SELECT type,is_active,is_global,count(*) FROM function GROUP BY type,is_active,is_global; SELECT id,is_active,is_global FROM function WHERE id IN ('\''pass_grade_to_gateway'\'','\''change_chat_title'\'');"'

Ran terminal command: printf 'Exact task-generation config keys in deployed image\n'; docker exec openwebui-lti sh -c 'grep -n -A 6 -B 1 -E "^ENABLE_(TITLE|TAGS|FOLLOW_UP)_GENERATION" /app/backend/open_webui/config.py'; printf '\nRemaining selected runtime signals\n'; uptime; printf '\nDocker storage totals\n'; docker system df --format 'table {{.Type}}\t{{.TotalCount}}\t{{.Size}}\t{{.Reclaimable}}'

Search for `gunicorn|DATABASE_URL|openwebui-shared-data|proxy_read_timeout|auth_request /...`

## Recommendation

**For 30 simultaneous users, I would start with one OCI Ampere A1 VM with 4 OCPUs, 24 GB RAM, and 100–150 GB of storage, keeping Docker Compose.** You do not need Kubernetes or a GPU for the current deployment.

Your existing **2-OCPU / 12-GB VM may already support 30 users doing ordinary API-backed chat**, but I would not promise that capacity without an end-to-end load test. There are application-level concurrency risks that a larger VM alone would not fix.

I inspected the repository, running containers, host resources, PostgreSQL configuration, and active nginx routing. **I made no deployment changes or load-generating model requests.** Moodle is excluded from this assessment.

## 1. What is running now

| Component | Observed configuration | Implication |
|---|---|---|
| OCI VM | `VM.Standard.A1.Flex`, **2 OCPUs / 12 GB RAM**, Santiago region | A reasonable starting point for externally hosted AI |
| Stock Open WebUI | `v0.12.2` | Shares database and files with the custom instance |
| Custom Open WebUI | `v0.12.3-arm` | Different version from the stock instance; compatibility needs attention |
| Model provider | Runtime and persisted configuration point to **Moonshot/Kimi**; Ollama is disabled | Model inference is external, so provider limits matter more than GPU capacity |
| Gateway | Two synchronous Gunicorn workers per Gateway container | Slow requests can delay other requests, including authentication checks |
| PostgreSQL | PostgreSQL 16; `max_connections=100`; database approximately **11 MB** | No immediate database-size concern |
| Memory | Approximately **8.2 GiB available** during inspection | No current memory pressure; this was not a loaded measurement |
| Storage | **38 GB used of 48 GB; 9.5 GB free** | Storage headroom is the most immediate infrastructure concern |

All four application health endpoints returned HTTP 200. That verifies readiness, **not capacity for 30 concurrent users**.

The main application definitions are in `the stock Open WebUI Compose configuration`, `the custom UI and Gateway Compose configuration`, and `the PostgreSQL Compose configuration`.

## 2. Main requirements and bottlenecks

### A. Provider capacity is essential

Because Kimi runs the model remotely, adding OCI CPUs will not solve upstream rate limits.

For example, assuming each of 30 users sends one request per minute:

| Workload assumption | Required capacity before headroom |
|---|---:|
| 1 request/minute/user | 30 requests/minute |
| 5,000 input tokens + 1,000 output tokens/request | Approximately 180,000 tokens/minute |
| Everyone submits together | A burst of 30 requests, potentially 30 concurrent generations |

These are planning examples, not measurements of your actual prompts. Long conversations, images, tool calls, and retries can increase demand significantly.

**Check your Kimi account’s concurrency, RPM, TPM, and daily limits for the models you use.** Target headroom above the measured workload—roughly 1.5–2× is a sensible initial planning margin. Kimi documents these limits [here](https://platform.kimi.ai/docs/pricing/limits).

### B. The Gateway can become a shared bottleneck

The `Gateway startup command` uses two synchronous workers. nginx also sends authentication subrequests to the Gateway for the custom UI.

The authentication handler itself is lightweight. However, `chat-resume lookup` can perform a sign-in, a chat listing, and up to 20 sequential chat-detail requests. Each HTTP request has a five-second timeout.

**Two slow lookups could therefore occupy both workers while unrelated users wait for authentication.** The Gateway does not carry the model stream itself, but it can delay access to the UI.

Recommendations:

- Give chat-resume lookup a bounded overall time budget.
- Avoid exhaustive sequential lookup on the critical access path where possible.
- Test a threaded Gunicorn configuration, such as **2 workers × 4 threads**, after validating library/thread safety and SQLite write contention.
- If contention remains, isolate lightweight authentication from slower Gateway operations.

I would address this before simply multiplying Open WebUI workers.

### C. Review enabled custom functions for blocking work

The supplied `grade-forwarding filter` makes a synchronous HTTP request. The deployed custom Open WebUI invokes synchronous filter handlers directly from its async processing path.

If that filter runs, a slow destination can block other work in that Open WebUI worker. Since Moodle is out of scope, **exclude external grade submission from this capacity target and disable the filter on models that do not need it**. If retained later, use nonblocking I/O or an appropriately designed background delivery mechanism.

The supplied `chat-title filter` also adds a 1.5-second wait. It is an asynchronous wait, so it is not the same blocking issue, but it adds latency wherever enabled.

### D. Do not scale the current stateful layout blindly

Both Open WebUI services share PostgreSQL and the same data volume. They currently use local file storage and default to embedded Chroma for vector storage.

That means:

- The two different application versions need **shared-schema and shared-data compatibility testing**. Pin a compatible stock/custom release pair and coordinate migrations.
- Embedded Chroma should not be treated as a safe shared multi-process vector service. If both frontends use RAG, move to a client-server vector database.
- Adding workers or replicas requires shared coordination, not just extra CPUs.

Open WebUI’s [scaling documentation](https://docs.openwebui.com/getting-started/advanced-topics/scaling) calls for PostgreSQL, Redis, shared file storage, and a client-server vector database when scaling workers or replicas.

## 3. Recommended OCI deployment

### First choice: one properly configured VM

```text
Users
  │ HTTPS
  ▼
nginx
  ├── Stock Open WebUI — administration
  ├── Custom Open WebUI — users
  └── Gateway — authentication / application integration
            │
            ▼
        PostgreSQL

Open WebUI ──HTTPS──► Kimi API
Backups    ────────► OCI Object Storage
```

| Resource | Recommended starting point |
|---|---|
| Compute | **VM.Standard.A1.Flex: 4 OCPUs / 24 GB RAM** |
| Storage | **100–150 GB total initially**, with measured growth and retention |
| Deployment | Existing Docker Compose approach |
| Open WebUI workers | Start with **one worker per frontend**; scale only after testing |
| Gateway | Test additional concurrency and bounded slow operations |
| Backups | Scheduled database, file, and Gateway-state backups off the VM |
| Monitoring | OCI Monitoring plus application/request metrics and alerts |

On A1, **one OCPU equals one CPU core/vCPU**; x86 OCI shapes count differently. See [OCI shape definitions](https://docs.oracle.com/en-us/iaas/Content/Compute/References/computeshapes.htm).

**Why this size:** it gives useful CPU and memory headroom for simultaneous page loads, uploads, database work, and document processing without introducing distributed-system complexity. It is a starting recommendation—not a measured minimum or capacity guarantee.

A cheaper path is to tune and test the existing 2-OCPU/12-GB VM first, then resize only if it misses the acceptance criteria.

### Storage and operational changes

I would prioritize these alongside compute sizing:

- **Expand storage before the next significant deployment.** Docker reports about 23 GB of images; rebuilding or pulling another large image could consume much of the remaining space.
- Configure Docker log rotation and deliberate old-image retention. Do not indiscriminately prune volumes.
- Consider a separate OCI Block Volume for persistent data.
- Back up PostgreSQL, uploads, Gateway SQLite databases, registrations, and signing keys. Protect credentials and keys in encrypted backups.
- Test restoration onto another VM. The existing `backup script` covers PostgreSQL and Open WebUI data, but the Gateway volumes need coverage too.
- Keep database and internal application ports private. PostgreSQL is currently published on all host interfaces; actual external reachability depends on host and OCI network rules.

Also, **do not assume 4 OCPUs/24 GB is free**. The [current Always Free documentation](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) lists A1 allowances equivalent to 2 OCPUs/12 GB. Confirm your tenancy’s allowance, regional availability, and current pricing.

## 4. When multiple OCI VMs are worthwhile

**Thirty users alone does not justify multiple VMs.**

| Layout | When to choose it |
|---|---|
| One VM for applications and PostgreSQL | Best initial cost/complexity balance |
| Application VM + private PostgreSQL VM | Database isolation, independent maintenance, or measured resource contention |
| Two application VMs + OCI Load Balancer + shared services | Availability requirements or demonstrated need for horizontal scaling |

Splitting the app and database across two VMs **does not by itself provide high availability**.

Before running replicated application instances, you would need:

- Redis for WebSocket/application coordination.
- Shared file storage or a tested object-storage integration.
- A client-server vector database if RAG is used.
- Shared secrets and compatible versions.
- An appropriate WebSocket/streaming load-balancer configuration.
- A centralized persistence design for the Gateway—**not independent SQLite copies or SQLite placed on a network share**.

For this target, I would avoid OKE/Kubernetes unless your team already operates it.

## 5. How to prove support for 30 simultaneous users

The acceptance test should exercise the **actual custom UI through nginx and Gateway authentication**, not just send requests directly to the model provider.

Use staging or a controlled maintenance window, with synthetic accounts and an agreed API-spend limit:

1. Ramp through **5 → 15 → 30 users**.
2. Have all 30 submit a message at approximately the same time.
3. Sustain realistic conversations for **30–60 minutes**, including growing chat histories.
4. Repeat with representative images/documents if those are part of normal use.
5. Test new-user provisioning, returning users, reconnects, and simultaneous Gateway access.
6. Add a short **45-user headroom test**.

Suggested initial acceptance targets:

| Metric | Target |
|---|---|
| App/authentication failures | No systematic failures; overall request failure rate below 1% |
| Ordinary non-generation API latency | p95 below 1 second |
| App-added time to first token | p95 below 1 second above a comparable direct-provider baseline |
| Streams | All 30 deliver complete responses without unexplained disconnections |
| Resources | No OOM/restarts, sustained CPU saturation, DB-pool exhaustion, or lock timeouts |
| Provider | No rate-limit failures at the agreed workload |

**Bottom line:** keep the architecture simple, fix the Gateway/blocking-function risks, expand storage, verify Kimi quotas, and load-test. **A single 4-OCPU/24-GB A1 VM is my recommended first production configuration; multiple OCI VMs should follow availability needs or measured bottlenecks, not the user count alone.**