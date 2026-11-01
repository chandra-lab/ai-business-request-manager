"""Groq provider unit tests — HTTP mocked; no live key required."""

from __future__ import annotations

import json

import httpx
import pytest

from app.ai.factory import get_ai_provider
from app.ai.groq_provider import GROQ_CHAT_URL, GroqAIProvider
from app.ai.mock_provider import MockAIProvider
from app.core.config import get_settings


def _groq_ok_payload(*, content: dict) -> dict:
    return {
        "id": "chatcmpl-test",
        "model": "openai/gpt-oss-20b",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(content),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 120, "completion_tokens": 40, "total_tokens": 160},
    }


def test_groq_analyze_request_parses_json(monkeypatch):
    get_settings.cache_clear()
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == GROQ_CHAT_URL
        assert request.headers.get("Authorization", "").startswith("Bearer ")
        body = json.loads(request.content.decode())
        captured["body"] = body
        assert body["model"] == "openai/gpt-oss-20b"
        assert body["response_format"] == {"type": "json_object"}
        assert body["messages"][0]["role"] == "system"
        return httpx.Response(
            200,
            json=_groq_ok_payload(
                content={
                    "recommended_department_code": "IT",
                    "confidence": 0.91,
                    "rationale": "VPN / access language maps to IT.",
                    "is_hr_sensitive": False,
                    "recommended_priority": "high",
                    "labels": ["it", "access"],
                }
            ),
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    provider = GroqAIProvider(
        api_key="gsk_test_not_real",
        model_id="openai/gpt-oss-20b",
        http_client=client,
    )
    result = provider.analyze_request(
        title="VPN access broken after password reset",
        description="Cannot connect to corporate VPN since resetting password.",
    )
    assert result.provider == "groq"
    assert result.model_id == "openai/gpt-oss-20b"
    assert result.recommendation.recommended_department_code == "IT"
    assert result.recommendation.confidence == 0.91
    assert result.recommendation.recommended_priority == "high"
    assert result.input_tokens == 120
    assert result.output_tokens == 40
    assert "VPN" in captured["body"]["messages"][1]["content"]
    client.close()


def test_groq_requires_api_key():
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        GroqAIProvider(api_key="")


def test_factory_groq_falls_back_to_mock_without_key(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("AI_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "")
    get_settings.cache_clear()
    provider = get_ai_provider()
    assert isinstance(provider, MockAIProvider)
    get_settings.cache_clear()


def test_factory_selects_groq_when_key_present(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("AI_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_factory")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-20b")
    get_settings.cache_clear()
    provider = get_ai_provider()
    assert isinstance(provider, GroqAIProvider)
    assert provider.model_id == "openai/gpt-oss-20b"
    get_settings.cache_clear()


def test_groq_http_error_raises(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "Invalid API Key"}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = GroqAIProvider(api_key="gsk_bad", http_client=client)
    with pytest.raises(httpx.HTTPStatusError):
        provider.analyze_request(title="Need help", description="Something is wrong somehow.")
    client.close()
