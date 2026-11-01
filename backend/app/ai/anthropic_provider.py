"""Anthropic Messages API provider (optional).

Default model ID from Anthropic docs: ``claude-haiku-5-5`` (Claude Haiku 5.5).
Override with ANTHROPIC_MODEL_ID. Requires ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import json
import re

from app.ai.prompt import PROMPT_VERSION, SYSTEM_PROMPT, build_user_payload
from app.ai.schemas import AIProviderResult, AIRoutingRecommendation
from app.core.config import get_settings

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


class AnthropicAIProvider:
    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_id: str | None = None,
        max_tokens: int | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.anthropic_api_key
        self.model_id = model_id or settings.anthropic_model_id
        self.max_tokens = max_tokens if max_tokens is not None else settings.anthropic_max_tokens
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for the Anthropic provider")

    def analyze_request(self, *, title: str, description: str) -> AIProviderResult:
        # Official SDK — imported lazily so Mock-only installs stay light in tests
        # if anthropic is present (it is pinned in requirements).
        from anthropic import Anthropic

        client = Anthropic(api_key=self.api_key)
        message = client.messages.create(
            model=self.model_id,
            max_tokens=self.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": build_user_payload(title=title, description=description),
                }
            ],
        )

        text_parts: list[str] = []
        for block in message.content:
            if getattr(block, "type", None) == "text":
                text_parts.append(block.text)
        text = "\n".join(text_parts).strip()
        payload = _parse_json_object(text)
        recommendation = AIRoutingRecommendation.model_validate(payload)

        usage = getattr(message, "usage", None)
        input_tokens = getattr(usage, "input_tokens", None) if usage else None
        output_tokens = getattr(usage, "output_tokens", None) if usage else None

        return AIProviderResult(
            recommendation=recommendation,
            provider=self.name,
            model_id=self.model_id,
            prompt_version=PROMPT_VERSION,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw_response={
                "message_id": getattr(message, "id", None),
                "model": getattr(message, "model", self.model_id),
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
            raise ValueError("Anthropic response did not contain a JSON object") from None
        return json.loads(match.group(0))
