# AIBRM — AI Business Request Manager

Internal request routing for an automotive group. Phases 1–2 delivered foundation + request management. **Phase 3** adds Mock/Anthropic AI analysis via Celery outbox workers.

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

## Mock AI demo (Phase 3)

1. Ensure Compose is up (`docker compose up --build`) with `AI_PROVIDER=mock` (default).
2. Sign in at http://localhost:5173 as `employee@aibrm.example.com`.
3. **New request** with an IT-like title, e.g. `VPN access broken after password reset`.
4. Open the request — status moves `submitted` → `ai_processing`; detail page polls until **AI analysis** appears (department, confidence, rationale).
5. `GET /api/v1/requests/{id}/analysis` returns the stored `AIAnalysis` (no Anthropic key needed).

Handoff for Phase 4: after analysis completes, the request **stays** in `ai_processing` with `AIAnalysis.status=completed`. Confidence-based routing to `pending_review` / assignment is Phase 4.

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

- **Mock**: keyword fixtures for six scenarios (IT, HR, Finance, Fleet, Legal, ambiguous). No network calls.
- **Anthropic**: official `anthropic` SDK; structured JSON validated by Pydantic; falls back to Mock if provider is `anthropic` but no key is set.
- Code lives under `backend/app/ai/` (interface, schemas, prompt `v1.0.0`, Mock, Anthropic, factory, service).

## Phase status

- **Phase 1**: foundation — Compose, auth, models, seed, login UI
- **Phase 2**: request CRUD/lifecycle, attachments, employee dashboard API + UI
- **Phase 3 (current)**: AI interface, Mock/Anthropic, Celery outbox consumer, analysis UI
- Phases 4–7: routing, security hardening, role dashboards, scenario validation
