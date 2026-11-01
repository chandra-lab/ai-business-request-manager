# AIBRM architecture

Modular monolith: FastAPI API + Celery workers + React SPA + Postgres + RabbitMQ.

```mermaid
flowchart TB
  subgraph clients [Clients]
    UI[React SPA Vite]
  end

  subgraph api [API process]
    FastAPI[FastAPI /api/v1]
    Authz[Authz + HR boundary]
    FastAPI --> Authz
  end

  subgraph data [Data plane]
    PG[(Postgres 16)]
    Outbox[(Transactional outbox)]
  end

  subgraph async [Async plane]
    RMQ[RabbitMQ]
    Worker[Celery worker]
    AI[AI providers Mock / Anthropic]
  end

  UI -->|JWT HTTPS| FastAPI
  FastAPI --> PG
  FastAPI -->|same TX| Outbox
  Outbox --> RMQ
  RMQ --> Worker
  Worker --> AI
  Worker -->|analysis + routing| PG
  Worker -->|retries / dead-letter → review| PG
```

## Request lifecycle (happy path)

```mermaid
stateDiagram-v2
  [*] --> draft
  draft --> submitted: requester submit
  submitted --> ai_processing: outbox worker
  ai_processing --> pending_assignment: confidence ≥ auto threshold\nand non-HR
  ai_processing --> pending_review: medium/low confidence\nor HR-sensitive or AI failure
  pending_review --> pending_assignment: reviewer assigns dept
  pending_assignment --> assigned: manager assigns employee
  assigned --> in_progress
  in_progress --> resolved
  resolved --> closed
  draft --> cancelled
  submitted --> cancelled
```

## Security boundary (Phase 5)

- Non-HR requests: requester, department manager (same dept), reviewers (pending_review), admins.
- HR-sensitive / highly confidential: **requester**, **HR role**, or **HRCaseAccess** grant only. Admins do **not** auto-receive HR content.
- `HRCaseNotes` are separate resources; requesters get 403 on notes.

## Reliability

- Submit enqueues `OutboxMessage` in the same DB transaction as the request.
- Celery consumes `request.submitted` → AI analysis → confidence routing.
- Retries with exponential backoff; exhausted attempts → manual review queue (never drop the request).
- Default `AI_PROVIDER=mock` so the system runs without Anthropic credentials.
