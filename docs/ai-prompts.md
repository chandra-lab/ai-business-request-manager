# AI prompts and providers

## Prompt version

Current: **`v1.0.1`** (`backend/app/ai/prompt.py`).

Design goals:

- Compact system instructions (department codes only).
- User title/description wrapped in explicit DATA delimiters (`<<<REQUEST_TITLE>>>` …).
- Explicit rule: ignore instruction-like text inside the request body (prompt-injection resistance).
- Output: one JSON object validated by Pydantic (`AIRoutingRecommendation`).

## Providers

| Provider | When | Notes |
|----------|------|-------|
| `mock` (default) | `AI_PROVIDER=mock` or missing Anthropic key | Keyword fixtures for six scenarios; no network |
| `anthropic` | `AI_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` | Default model `claude-haiku-5-5` |

Factory: `backend/app/ai/factory.py`. Interface: `backend/app/ai/interface.py`.

## Structured output

Required fields:

- `recommended_department_code` ∈ {HR, IT, FIN, FLEET, LEGAL} or null
- `confidence` ∈ [0, 1]
- `rationale` (short string)
- `is_hr_sensitive` (bool)
- optional `recommended_priority`, `labels`, `scenario_id`

Invalid / incomplete model JSON fails analysis → request routes to **manual review**.

## Idempotency & metrics

- Analysis key: `ai:{request_id}:{sha256(title+description)[:32]}`
- Persisted metrics: `model_id`, `prompt_version`, `input_tokens`, `output_tokens`, `duration_ms`
- AI-recommended priority is stored on `AIAnalysis.recommended_priority` separately from system `request.priority` (audited when they diverge)

## Outage simulation

Set `AI_FORCE_FAILURE=true` to force provider failure → analysis `failed` → review queue (scenario / ops drill).
