# AIBRM — AI Business Request Manager

Internal request routing for an automotive group. **Phase 5** adds department/HR authorization, case grants, and audit logging.

Works **without an Anthropic API key** — `AI_PROVIDER=mock` is the default.

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
| employee@aibrm.example.com  | employee                     |
| manager@aibrm.example.com   | employee, department_manager |
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
  -d '{"title":"Need badge access","description":"Cannot enter building B after hours.","priority":"high","submit":true}'

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
- `AI_PROVIDER=mock` — no Anthropic key required
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

| Setting | Purpose |
|---------|---------|
| `AI_PROVIDER` | `mock` (default) or `anthropic` |
| `ANTHROPIC_API_KEY` | Required only when `AI_PROVIDER=anthropic` |
| `ANTHROPIC_MODEL_ID` | Default **`claude-haiku-5-5`** ([Anthropic Haiku 5.5 docs](https://platform.claude.com/docs/en/models/haiku-5-5/overview)) |
| `ANTHROPIC_MAX_TOKENS` | Default `512` |
| `AI_FORCE_FAILURE` | Simulate provider outage → analysis failure → review |
| `ROUTING_AUTO_ASSIGN_MIN` | Default `0.85` auto department |
| `ROUTING_REVIEW_MIN` | Default `0.60` (below → clarification review) |
| `OUTBOX_MAX_ATTEMPTS` | Default `5`; then dead-letter to manual review |

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

- **Department scope**: managers/dept users see non-HR requests for their department; reviewers see non-HR `pending_review`.
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
- **Phase 5 (current)**: department/HR security, case grants, audit, injection tests
- Phases 6–7: dashboard polish, scenario validation
