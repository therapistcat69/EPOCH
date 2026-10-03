import json

import httpx
import pytest
import respx

from app.errors import AppError
from app.schemas.reports import GroqChannelReport
from app.services.groq_service import GroqService

BASE = "https://api.groq.com/openai/v1"


def chat(content):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


VALID = json.dumps({"summary": "ok", "strengths": ["a"], "recommendations": [{"observation": "o", "interpretation": "i", "recommendation": "r"}]})


@respx.mock
async def test_chat_json_valid_uses_configured_model():
    route = respx.post(f"{BASE}/chat/completions").mock(return_value=chat(VALID))
    out = await GroqService().chat_json("sys", "user", GroqChannelReport)
    assert out.summary == "ok" and out.recommendations[0].recommendation == "r"
    body = json.loads(route.calls[0].request.content)
    assert body["model"] == "test-chat-model" and body["response_format"] == {"type": "json_object"}  # not hardcoded
    assert route.calls[0].request.headers["authorization"] == "Bearer test-groq-key"


@respx.mock
async def test_invalid_json_retries_once_with_correction_prompt():
    route = respx.post(f"{BASE}/chat/completions").mock(side_effect=[chat("not json at all"), chat(VALID)])
    out = await GroqService().chat_json("sys", "user", GroqChannelReport)
    assert out.summary == "ok" and route.call_count == 2
    second = json.loads(route.calls[1].request.content)["messages"]
    assert "not valid" in second[-1]["content"]


@respx.mock
async def test_still_invalid_returns_controlled_error_without_raw_output():
    respx.post(f"{BASE}/chat/completions").mock(return_value=chat('{"wrong": "schema"}'))
    with pytest.raises(AppError) as e:
        await GroqService().chat_json("sys", "user", GroqChannelReport)
    assert e.value.code == "GROQ_INVALID_RESPONSE" and "wrong" not in e.value.message


@respx.mock
@pytest.mark.parametrize("status,code", [(429, "GROQ_RATE_LIMITED"), (401, "GROQ_AUTH_FAILED"), (503, "GROQ_UNAVAILABLE")])
async def test_error_mapping(status, code):
    respx.post(f"{BASE}/chat/completions").mock(return_value=httpx.Response(status, json={"error": {"message": "secret detail"}}))
    with pytest.raises(AppError) as e:
        await GroqService().chat_json("s", "u", GroqChannelReport)
    assert e.value.code == code and "secret detail" not in e.value.message


@respx.mock
async def test_timeout_mapped():
    respx.post(f"{BASE}/chat/completions").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(AppError) as e:
        await GroqService().chat_json("s", "u", GroqChannelReport)
    assert e.value.code == "GROQ_TIMEOUT"


async def test_not_configured():
    with pytest.raises(AppError) as e:
        await GroqService(api_key="").chat_json("s", "u", GroqChannelReport)
    assert e.value.code == "GROQ_NOT_CONFIGURED"


@respx.mock
async def test_transcribe_maps_verbose_json_segments():
    route = respx.post(f"{BASE}/audio/transcriptions").mock(return_value=httpx.Response(200, json={
        "language": "hi", "duration": 12.5, "text": "namaste dosto",
        "segments": [{"id": 0, "start": 0.0, "end": 4.2, "text": " namaste "}, {"id": 1, "start": 4.2, "end": 12.5, "text": "dosto"}],
    }))
    res = await GroqService().transcribe(b"audio-bytes", "a.mp3", None)
    assert res.language == "hi" and [s.text for s in res.segments] == ["namaste", "dosto"] and res.segments[1].end == 12.5
    sent = route.calls[0].request.content
    assert b"verbose_json" in sent and b"test-stt-model" in sent and b"timestamp_granularities" in sent
    assert b'name="language"' not in sent  # auto-detect for Hindi/Hinglish/multilingual


@respx.mock
async def test_transcribe_empty_speech():
    respx.post(f"{BASE}/audio/transcriptions").mock(return_value=httpx.Response(200, json={"text": "", "segments": []}))
    with pytest.raises(AppError) as e:
        await GroqService().transcribe(b"x", "a.mp3")
    assert e.value.code == "TRANSCRIPTION_EMPTY"
