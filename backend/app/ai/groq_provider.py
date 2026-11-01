"""Groq OpenAI-compatible Chat Completions provider.

Uses ``POST https://api.groq.com/openai/v1/chat/completions`` with JSON object mode.
Default model ``openai/gpt-oss-20b`` (Groq production models list —
https://console.groq.com/docs/models). Override with ``GROQ_MODEL``
(e.g. ``llama-3.1-8b-instant`` when your Groq account has access).
Requires ``GROQ_API_KEY`` when ``AI_PROVIDER=groq``.
"""

from __future__ import annotations

import json
import re

import httpx

from app.ai.prompt import PROMPT_VERSION, SYSTEM_PROMPT, build_user_payload
from app.ai.schemas import AIProviderResult, AIRoutingRecommendation
from app.core.config import get_settings

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqAIProvider:
    name = "groq"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_id: str | None = None,
        max_tokens: int | None = None,
        timeout_seconds: float = 60.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.groq_api_key
        self.model_id = model_id or settings.groq_model
        self.max_tokens = max_tokens if max_tokens is not None else settings.groq_max_tokens
        self.timeout_seconds = timeout_seconds
        self._http_client = http_client
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY is required for the Groq provider")

    def analyze_request(self, *, title: str, description: str) -> AIProviderResult:
        body = {
            "model": self.model_id,
            "temperature": 0.1,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_user_payload(title=title, description=description),
                },
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if self._http_client is not None:
            response = self._http_client.post(GROQ_CHAT_URL, headers=headers, json=body)
        else:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(GROQ_CHAT_URL, headers=headers, json=body)

        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise ValueError("Groq response contained no choices")
        message = choices[0].get("message") or {}
        text = (message.get("content") or "").strip()
        payload = _parse_json_object(text)
        recommendation = AIRoutingRecommendation.model_validate(payload)

        usage = data.get("usage") or {}
        return AIProviderResult(
            recommendation=recommendation,
            provider=self.name,
            model_id=data.get("model") or self.model_id,
            prompt_version=PROMPT_VERSION,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            raw_response={
                "id": data.get("id"),
                "model": data.get("model"),
                "content_text": text,
                "parsed": payload,
            },
        )


def _parse_json_object(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_OBJECT.search(text)
        if not match:
            raise ValueError("Groq response did not contain a JSON object") from None
        return json.loads(match.group(0))
