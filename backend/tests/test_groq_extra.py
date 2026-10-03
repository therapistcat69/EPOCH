import json

import httpx
import pytest
import respx

from app.errors import AppError
from app.schemas.reports import GroqChannelReport
from app.services.groq_service import GroqService

BASE = "https://api.groq.com/openai/v1"
OK = httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"summary": "ok"})}}]})


@respx.mock
async def test_reasoning_model_gets_headroom_and_low_effort(monkeypatch):
    monkeypatch.setenv("GROQ_CHAT_MODEL", "openai/gpt-oss-120b")
    from app.config import get_settings

    get_settings.cache_clear()
    route = respx.post(f"{BASE}/chat/completions").mock(return_value=OK)
    await GroqService().chat_json("s", "u", GroqChannelReport, max_tokens=300)
    body = json.loads(route.calls[0].request.content)
    assert body["reasoning_effort"] == "low" and body["max_tokens"] >= 6000


@respx.mock
async def test_non_reasoning_model_has_no_reasoning_param():
    route = respx.post(f"{BASE}/chat/completions").mock(return_value=OK)  # conftest model: test-chat-model
    await GroqService().chat_json("s", "u", GroqChannelReport, max_tokens=300)
    body = json.loads(route.calls[0].request.content)
    assert "reasoning_effort" not in body and body["max_tokens"] == 300


@respx.mock
async def test_400_json_validate_failed_is_retried_once():
    route = respx.post(f"{BASE}/chat/completions").mock(side_effect=[httpx.Response(400, json={"error": {"code": "json_validate_failed"}}), OK])
    out = await GroqService().chat_json("s", "u", GroqChannelReport)
    assert out.summary == "ok" and route.call_count == 2


@respx.mock
async def test_400_twice_returns_controlled_error():
    respx.post(f"{BASE}/chat/completions").mock(return_value=httpx.Response(400, json={"error": {"code": "json_validate_failed"}}))
    with pytest.raises(AppError) as e:
        await GroqService().chat_json("s", "u", GroqChannelReport)
    assert e.value.code == "GROQ_INVALID_RESPONSE"
