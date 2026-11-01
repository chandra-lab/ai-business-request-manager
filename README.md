# AIBRM — AI Business Request Manager

Internal request routing for an automotive group. Phase 1 delivers the foundation: Docker Compose stack, FastAPI auth, SQLAlchemy schema + Alembic, seed data, and a React login shell.

Works **without an Anthropic API key** (Mock AI is the default; AI processing arrives in Phase 3).

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

| Email                 | Roles                         |
|-----------------------|-------------------------------|
| employee@aibrm.example.com  | employee                      |
| manager@aibrm.example.com   | employee, department_manager  |
| reviewer@aibrm.example.com  | employee, reviewer            |
| hr@aibrm.example.com        | employee, hr                  |
| admin@aibrm.example.com     | employee, admin               |

Password for all demo users: value of `SEED_DEMO_PASSWORD` in `.env` / `.env.example`.

## Project layout

```
ai-business-request-manager/
├── backend/          # FastAPI modular monolith
├── frontend/         # Vite + React + TypeScript + Tailwind
├── docker-compose.yml
├── .env.example
└── README.md
```

Backend modules: `auth`, `users`, `departments`, `requests`, `ai`, `routing`, `assignments`, `notifications`, `audit`, `workers`.

## Local development (without Compose for the API)

Requirements: Python 3.12+, Node 20+, PostgreSQL 16, RabbitMQ (optional for API-only).

```bash
# Database (example via Compose infra only)
docker compose up -d postgres rabbitmq

# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # set POSTGRES_HOST=localhost and DATABASE_URL accordingly
alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload --port 8000

# Frontend
cd ../frontend
npm install
npm run dev
```

## Smoke tests

```bash
cd backend
source .venv/bin/activate
# DATABASE_URL / TEST_DATABASE_URL must point at a reachable Postgres
pytest -q
```

Covers: `GET /health`, login, `GET /api/v1/auth/me`.

## Configuration

Copy `.env.example` → `.env`. Important variables:

- `JWT_SECRET` — min 32 chars; change for any shared environment
- `DATABASE_URL` / Postgres credentials
- `CELERY_BROKER_URL` / RabbitMQ credentials
- `AI_PROVIDER=mock` — no Anthropic key required
- `ANTHROPIC_API_KEY` — optional, unused until Phase 3
- `SEED_DEMO_PASSWORD` — demo user password for the seed script

## Auth API (Phase 1)

| Method | Path                     | Notes                          |
|--------|--------------------------|--------------------------------|
| POST   | `/api/v1/auth/login`     | email + password → JWT pair    |
| POST   | `/api/v1/auth/refresh`   | refresh → new JWT pair         |
| POST   | `/api/v1/auth/logout`    | authenticated; client drops tokens |
| GET    | `/api/v1/auth/me`        | current user + roles           |

Swagger UI: `/docs`.

## Schema (Phase 1)

Tables: Users, Departments, Roles, UserRoles, Requests, AIAnalysis, Assignments, RequestHistory, Attachments, AuditLogs, HRCaseAccess, RequestReviewQueue, OutboxMessages, plus protected **HRCaseNotes**.

## Phase status

- **Phase 1 (this repo)**: foundation — Compose, auth, models, seed, login UI, smoke tests
- Phases 2–7: request CRUD, AI, routing, security hardening, dashboards, scenario validation
