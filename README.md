# AIBRM — AI Business Request Manager

Internal request routing for an automotive group. **Phase 7** adds mandatory scenario automation and product docs.

Works **without an Anthropic API key** — `AI_PROVIDER=mock` is the default.

### Docs

| Doc | Path |
|-----|------|
| Architecture | [`docs/architecture.md`](docs/architecture.md) |
| AI prompts | [`docs/ai-prompts.md`](docs/ai-prompts.md) |
| Scenarios 1–6 | [`docs/scenarios.md`](docs/scenarios.md) |
| Limitations | [`docs/limitations.md`](docs/limitations.md) |

Assessment pack teams (for admin create / mapping notes): `IT Support`, `Finance`, `Operations`, `HR Operations`, `Restricted HR Review`, `General Administration`, `Manual Review` — see store pack `internal/assessment-data-pack/.../teams.csv`. Full CSV import is out of scope; admins create departments in **Admin → Departments** (`/app/admin/departments`).

## Quick start (Docker Compose)

```bash
cp .env.example .env
docker compose up --build
```

Services:

| Service   | URL                          |
|-----------|------------------------------|
| Frontend  | http://localhost:5173        |
| API docs  | http://localhost:8000/docs   |
| Health    | http://localhost:8000/health |
| RabbitMQ  | http://localhost:15672       |

On first API start Compose runs `alembic upgrade head` and the seed script.

## Demo credentials

Seeded by `backend/scripts/seed.py` using `SEED_DEMO_PASSWORD` from `.env` (default `DemoPass123!`).

| Email                       | Roles                        |
|-----------------------------|------------------------------|
| employee@aibrm.example.com  | employee (IT)                |
| manager@aibrm.example.com   | department_manager (**IT**)  |
| fleet.manager@aibrm.example.com | department_manager (FLEET) |
| reviewer@aibrm.example.com  | employee, reviewer           |
| hr@aibrm.example.com        | employee, hr                 |
| admin@aibrm.example.com     | employee, admin              |

## Phase 4 demo — auto IT + ambiguous review

Thresholds (env): `ROUTING_AUTO_ASSIGN_MIN=0.85`, `ROUTING_REVIEW_MIN=0.60`.

**Auto-route (high confidence IT)**  
1. Login as `employee@aibrm.example.com`.  
2. Submit: title `VPN access broken after password reset`.  
3. Status becomes `pending_assignment` with department IT (no individual yet).  
4. Login as `manager@aibrm.example.com` → **Manager queue** → assign an employee.

**Ambiguous → review**  
1. Submit: title `Need help` / vague description.  
2. Status `pending_review`, clarification required.  
3. Login as `reviewer@aibrm.example.com` or `admin@…` → **Review queue** → assign department or request information.

Simulate AI outage → manual review: set `AI_FORCE_FAILURE=true` (or exhaust outbox retries).

API equivalent:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"employee@aibrm.example.com","password":"DemoPass123!"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

curl -s -X POST http://localhost:8000/api/v1/requests \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: demo-1' \
  -d '{"title":"Need badge access","description":"Cannot enter building B after hours.","submit":true}'

curl -s http://localhost:8000/api/v1/requests -H "Authorization: Bearer $TOKEN"
curl -s http://localhost:8000/api/v1/dashboard/employee -H "Authorization: Bearer $TOKEN"
```

## Project layout

```
ai-business-request-manager/
├── backend/          # FastAPI modular monolith
├── frontend/         # Vite + React + TypeScript + Tailwind
├── docker-compose.yml
├── .env.example
└── README.md
```

## Local development (without full Compose for the API)

```bash
docker compose up -d postgres rabbitmq
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head && python -m scripts.seed
uvicorn app.main:app --reload --port 8000
# frontend
cd ../frontend && npm install && npm run dev
```

## Tests

```bash
cd backend && source .venv/bin/activate
pytest -q
```

Covers health, auth, request create/list/detail/history, idempotency, authz, attachments, employee dashboard.

## Configuration

- `JWT_SECRET` — min 32 chars
- `DATABASE_URL` / Postgres credentials
- `CELERY_BROKER_URL` / RabbitMQ credentials
- `AI_PROVIDER=mock` — default. Live: `groq` (`GROQ_API_KEY`, `GROQ_MODEL=openai/gpt-oss-20b`) or `anthropic` (`ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`)
- `SEED_DEMO_PASSWORD` — demo user password for the seed script
- `UPLOAD_DIR` — local attachment storage (default `uploads`)
- `UPLOAD_MAX_BYTES` — default 10 MiB
- `UPLOAD_ALLOWED_CONTENT_TYPES` — CSV of MIME types

## Auth API (Phase 1)

| Method | Path                   | Notes |
|--------|------------------------|-------|
| POST   | `/api/v1/auth/login`   | email + password → JWT pair |
| POST   | `/api/v1/auth/refresh` | refresh → new JWT pair |
| POST   | `/api/v1/auth/logout`  | authenticated; client drops tokens |
| GET    | `/api/v1/auth/me`      | current user + roles |

## Requests API (Phase 2)

Paths are under `/api/v1` (same prefix as auth).

| Method | Path | Notes |
|--------|------|-------|
| POST   | `/api/v1/requests` | Create (JWT requester). Header `Idempotency-Key` optional; replay returns same row |
| GET    | `/api/v1/requests` | List/filter (`status`, `priority`, `page`, `page_size`). Employees: own; managers: dept; reviewers: pending_review; admin: all |
| GET    | `/api/v1/requests/{id}` | Detail + attachments metadata |
| PATCH  | `/api/v1/requests/{id}` | Draft edits; submit; cancel; submitted description clarification; narrow manager progress |
| GET    | `/api/v1/requests/{id}/history` | RequestHistory timeline |
| GET    | `/api/v1/requests/{id}/analysis` | Latest AIAnalysis (404 until worker completes) |
| POST   | `/api/v1/requests/{id}/attachments` | Multipart `file`; content-type + size checks |
| GET    | `/api/v1/requests/{id}/attachments/{aid}` | Download |
| GET    | `/api/v1/dashboard/employee` | Counts + recent requests for current user |

### Lifecycle (validated)

`draft → submitted → ai_processing → pending_review|assigned → in_progress → resolved → closed`, plus `cancelled` from most non-terminal states.

Phase 3 worker: on `request.submitted` outbox → `submitted` → `ai_processing`, one LLM/fixture call, persist `AIAnalysis`, leave status at `ai_processing` for Phase 4 routing. Analysis is idempotent for unchanged title/description.

## AI providers (Phase 3)

**Default is Mock** — no live API key required for local demo or CI.

### Groq (recommended live provider)

Uses Groq’s OpenAI-compatible Chat Completions API
(`https://api.groq.com/openai/v1/chat/completions`) with JSON object mode.

Default model: **`openai/gpt-oss-20b`** from Groq’s
[production models](https://console.groq.com/docs/models) (small / inexpensive;
verified against the Models API). Other production chat IDs such as
[`llama-3.1-8b-instant`](https://console.groq.com/docs/model/llama-3.1-8b-instant)
work when your Groq project has access — set `GROQ_MODEL` accordingly.

```bash
AI_PROVIDER=groq
GROQ_API_KEY=gsk_...          # from vault / Codespaces Secrets — never commit
GROQ_MODEL=openai/gpt-oss-20b # optional override
```

### Store secrets in GitHub Codespaces (recommended)

Do **not** commit API keys. Put them in the repo’s Codespaces secret vault:

1. Open the GitHub repository in the browser.
2. Go to **Settings** → **Secrets and variables** → **Codespaces**  
   Console path: `Settings → Secrets and variables → Codespaces`  
   Direct URL pattern: `https://github.com/<owner>/<repo>/settings/secrets/codespaces`
3. Click **New repository secret** and add:
   - `GROQ_API_KEY` — your Groq key (value only; name must match exactly)
   - `AI_PROVIDER` — value `groq`
   - `GROQ_MODEL` — optional; e.g. `openai/gpt-oss-20b` (Compose/app default if omitted)
4. **Rebuild the codespace** (or open a new codespace) so secrets are injected into the environment. Codespaces exports repository Codespaces secrets as environment variables inside the codespace.
5. Recreate API/worker containers so they pick up the new env:

```bash
docker compose up -d --force-recreate api worker
# or full stack:
docker compose down && docker compose up --build -d
```

`docker-compose.yml` passes `AI_PROVIDER`, `GROQ_API_KEY`, and `GROQ_MODEL` from the host environment into the **api** and **worker** services (and may also load an optional gitignored `.env`). Host/Codespaces env wins for those variables.

Local alternative: `cp .env.example .env` and fill placeholders in the gitignored `.env` only — never stage or commit that file.

### Anthropic (optional)

```bash
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-haiku-5-5
```

| Setting | Purpose |
|---------|---------|
| `AI_PROVIDER` | `mock` (**default**), `groq`, or `anthropic` |
| `GROQ_API_KEY` | Required only when `AI_PROVIDER=groq` |
| `GROQ_MODEL` | Default **`openai/gpt-oss-20b`** ([Groq models](https://console.groq.com/docs/models)); e.g. `llama-3.1-8b-instant` if available on your account |
| `GROQ_MAX_TOKENS` | Default `512` |
| `ANTHROPIC_API_KEY` | Required only when `AI_PROVIDER=anthropic` |
| `ANTHROPIC_MODEL` | Claude model id (default **`claude-haiku-5-5`**). Alias: `ANTHROPIC_MODEL_ID` |
| `ANTHROPIC_MAX_TOKENS` | Default `512` |
| `AI_FORCE_FAILURE` | Simulate provider outage → analysis failure → review |
| `ROUTING_AUTO_ASSIGN_MIN` | Default `0.85` auto department |
| `ROUTING_REVIEW_MIN` | Default `0.60` (below → clarification review) |
| `OUTBOX_MAX_ATTEMPTS` | Default `5`; then dead-letter to manual review |

If `AI_PROVIDER` is `groq`/`anthropic` but the matching key is empty, the factory falls back to **Mock** so the app still boots.

### Routing APIs (Phase 4)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/review-queue` | Open/in-review items |
| GET | `/api/v1/review-queue/{id}` | Detail |
| POST | `/api/v1/review-queue/{id}/assign-department` | Reviewer assigns department |
| POST | `/api/v1/review-queue/{id}/request-information` | Ask requester for clarification |
| GET | `/api/v1/manager/queue` | `pending_assignment` for manager’s dept |
| POST | `/api/v1/requests/{id}/assign` | Assign individual (idempotent) |
| POST | `/api/v1/requests/{id}/reassign` | Reassign individual |
| GET | `/api/v1/departments` | Active departments |
| GET | `/api/v1/notifications` | In-app notifications |

AI-recommended priority is stored on `AIAnalysis.recommended_priority` and audited separately from system `request.priority`.

## Security (Phase 5)

- **Department scope**: managers and **department members** see non-HR requests for their department (routed statuses); reviewers see non-HR `pending_review` (and may assign a department member from Actions).
- **HR boundary**: `is_hr_sensitive` / `highly_confidential` cases are visible to the **requester**, **HR role**, or users with an explicit `HRCaseAccess` grant only.
- **Admins do not auto-get HR content** — grant required (or HR role).
- **HRCaseNotes** are separate from request body; requesters can open their case but get **403** on notes.
- Denied HR view/content attempts are written to `audit_logs`.
- Attachment downloads use the same visibility rules (requester or HR principals on HR cases).
- Prompt injection: user title/description are delimited DATA; Mock scenario 5 (Legal) still wins when legal keywords are present alongside override text.

| Method | Path | Notes |
|--------|------|-------|
| GET/POST | `/api/v1/requests/{id}/hr-notes` | HR notes (HR role / grant) |
| GET/POST | `/api/v1/requests/{id}/hr-access` | List / grant case access |
| DELETE | `/api/v1/requests/{id}/hr-access/{access_id}` | Revoke grant |

Demo HR account: `hr@aibrm.example.com` / `DemoPass123!`

## Phase status

- **Phase 1**: foundation
- **Phase 2**: request management
- **Phase 3**: AI Mock/Anthropic + outbox
- **Phase 4**: confidence routing, review queue, manager assign, retries
- **Phase 5**: department/HR security, case grants, audit, injection tests
- **Phase 6**: employee / department / manager / review / HR dashboards; SSE+poll live status
- **Phase 7 (current)**: six mandatory scenarios automated; architecture / prompt / scenario / limitations docs

### Run tests

```bash
cd backend && source .venv/bin/activate
export APP_ENV=test UPLOAD_DIR=/tmp/aibrm-test-uploads
pytest -q
```

### Phase 6 UI routes

| Path | Role | Purpose |
|------|------|---------|
| `/app` | employee | My requests |
| `/app/department` | manager / admin | Department workload |
| `/app/manager` | manager / admin | Assign individuals |
| `/app/review` | reviewer / admin | Human review queue |
| `/app/hr` | hr | HR cases + internal notes |
| `/app/requests/:id` | scoped | Detail with SSE + polling |

Dashboard APIs: `GET /api/v1/dashboard/{employee,department,review,hr}` · Live: `GET /api/v1/requests/{id}/events`
