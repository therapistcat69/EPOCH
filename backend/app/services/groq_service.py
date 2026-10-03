"""Groq integration: Whisper speech-to-text and structured LLM reasoning.

The LLM is an explanation layer only: every number comes from YouTube APIs or deterministic
calculations. JSON output is validated with Pydantic; invalid output is retried once, then a
controlled error is raised (raw model output is never exposed).
"""
import json
import logging
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.errors import AppError
from app.services import usage

logger = logging.getLogger("retention.groq")
T = TypeVar("T", bound=BaseModel)


class TranscriptionSegment(BaseModel):
    segment_id: int
    start: float
    end: float
    text: str


class TranscriptionResult(BaseModel):
    language: str | None = None
    duration: float | None = None
    text: str
    segments: list[TranscriptionSegment]
    words: list[dict] | None = None


def _map_error(status: int) -> AppError:
    if status == 401:
        return AppError("GROQ_AUTH_FAILED", "The Groq API key was rejected. Check GROQ_API_KEY on the server.", 502)
    if status == 429:
        return AppError("GROQ_RATE_LIMITED", "Groq is rate limiting requests. Please retry in a moment.", 429)
    if status == 413:
        return AppError("AUDIO_TOO_LARGE", "That audio file is too large for transcription.", 413)
    if status in (400, 422):
        return AppError("GROQ_BAD_REQUEST", "Groq couldn't process that request (unsupported file or model).", 400)
    return AppError("GROQ_UNAVAILABLE", "Groq is temporarily unavailable. Please try again.", 502)


class GroqService:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        s = get_settings()
        self._key = api_key if api_key is not None else s.groq_api_key
        self._base = (base_url or s.groq_api_base).rstrip("/")
        self._chat_model = s.chat_model
        self._stt_model = s.transcription_model

    @property
    def configured(self) -> bool:
        return bool(self._key)

    def _require(self) -> None:
        if not self._key:
            raise AppError(
                "GROQ_NOT_CONFIGURED",
                "AI reports aren't available: GROQ_API_KEY is not set on the server.",
                503,
            )

    async def _post(self, path: str, *, timeout: float, **kw) -> dict:
        self._require()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    f"{self._base}/{path}", headers={"Authorization": f"Bearer {self._key}"}, **kw
                )
        except httpx.TimeoutException:
            raise AppError("GROQ_TIMEOUT", "Groq took too long to respond. Please try again.", 504)
        except httpx.HTTPError:
            raise AppError("GROQ_UNAVAILABLE", "Could not reach Groq. Please try again.", 502)
        if resp.status_code >= 400:
            logger.warning("Groq %s returned %s", path, resp.status_code)  # never log bodies or keys
            raise _map_error(resp.status_code)
        return resp.json()

    # ---- speech-to-text -------------------------------------------------------
    async def transcribe(
        self, content: bytes, filename: str, language: str | None = None, want_words: bool = False
    ) -> TranscriptionResult:
        usage.track("groq_transcription_calls")
        data: dict = {
            "model": self._stt_model,
            "response_format": "verbose_json",
            "timestamp_granularities[]": ["segment", "word"] if want_words else ["segment"],
        }
        if language:  # omit to let Whisper auto-detect (English, Hindi, Hinglish, multilingual)
            data["language"] = language
        raw = await self._post("audio/transcriptions", timeout=180, data=data, files={"file": (filename, content)})
        segments = [
            TranscriptionSegment(segment_id=int(s.get("id", i)), start=float(s["start"]), end=float(s["end"]), text=str(s["text"]).strip())
            for i, s in enumerate(raw.get("segments") or [])
            if str(s.get("text", "")).strip()
        ]
        if not segments and raw.get("text"):
            segments = [TranscriptionSegment(segment_id=0, start=0.0, end=float(raw.get("duration") or 0), text=raw["text"].strip())]
        if not segments:
            raise AppError("TRANSCRIPTION_EMPTY", "No speech was detected in that audio.", 422)
        return TranscriptionResult(
            language=raw.get("language"), duration=raw.get("duration"), text=raw.get("text", "").strip(),
            segments=segments, words=raw.get("words") if want_words else None,
        )

    # ---- structured reasoning ---------------------------------------------------
    async def chat_json(self, system: str, user: str, schema: type[T], max_tokens: int = 2500) -> T:
        """Request JSON, validate with Pydantic, retry once with a correction prompt."""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        last_error = ""
        payload: dict = {"model": self._chat_model, "temperature": 0.2, "response_format": {"type": "json_object"}}
        if "gpt-oss" in self._chat_model.lower():
            # Reasoning models spend part of max_tokens on hidden reasoning; a small budget truncates the JSON.
            payload["reasoning_effort"] = "low"
            max_tokens = max(max_tokens, 6000)
        payload["max_tokens"] = max_tokens
        for attempt in range(2):
            usage.track("groq_report_calls")
            try:
                raw = await self._post("chat/completions", timeout=120, json={**payload, "messages": messages})
            except AppError as exc:
                if exc.code != "GROQ_BAD_REQUEST":
                    raise
                # Groq answers 400 (json_validate_failed) when the model's JSON was malformed/truncated: retry once
                logger.warning("Groq rejected the model's JSON (attempt %s)", attempt + 1)
                last_error = "json_validate_failed"
                continue
            try:
                content = raw["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                content = ""
            try:
                return schema.model_validate(json.loads(content))
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = str(exc)[:400]
                logger.warning("Groq returned invalid structured output (attempt %s)", attempt + 1)
                messages = messages + [
                    {"role": "assistant", "content": content[:4000]},
                    {
                        "role": "user",
                        "content": "That response was not valid for the required JSON schema. "
                        f"Errors: {last_error}. Reply again with ONLY a corrected JSON object.",
                    },
                ]
        raise AppError(
            "GROQ_INVALID_RESPONSE",
            "The AI service returned an unusable response. Please try again.",
            502,
        )


def get_groq_service() -> GroqService:
    return GroqService()
