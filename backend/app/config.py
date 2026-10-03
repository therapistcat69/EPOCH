from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Search for .env in: backend dir → EPOCH root → kjsit root
_HERE = Path(__file__).resolve().parent.parent  # d:\kjsit\EPOCH\backend
_CANDIDATES = [
    _HERE / ".env",              # d:\kjsit\EPOCH\backend\.env
    _HERE.parent / ".env",       # d:\kjsit\EPOCH\.env
    _HERE.parent.parent / ".env" # d:\kjsit\.env
]
_ENV_FILE = next((str(p) for p in _CANDIDATES if p.exists()), ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore", populate_by_name=True)

    youtube_api_key: str = ""
    database_url: str = ""
    cache_ttl_hours: int = 6
    youtube_api_base: str = "https://www.googleapis.com/youtube/v3"

    # URLs (FRONTEND_ORIGIN is the legacy name for FRONTEND_URL)
    frontend_url: str = Field(
        "http://localhost:3000", validation_alias=AliasChoices("FRONTEND_URL", "FRONTEND_ORIGIN")
    )
    backend_url: str = "http://localhost:8000"

    # Google OAuth 2.0 (web application client). Creator mode only.
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/youtube/callback"
    session_secret: str = ""
    session_ttl_days: int = 14

    # Creator-mode tuning
    analytics_cache_minutes: int = 60
    max_sync_videos: int = 1000

    # Groq (speech-to-text + LLM reasoning). Models are env-configurable; blanks fall back to defaults.
    groq_api_key: str = ""
    groq_transcription_model: str = ""
    groq_chat_model: str = ""
    groq_api_base: str = "https://api.groq.com/openai/v1"
    max_audio_mb: int = 24  # Groq's upload limit is 25 MB

    # ML ops: retraining/promotion endpoints need this token (or a loopback client when unset, i.e. local development)
    admin_token: str = ""
    retrain_after_real_labels: int = 20
    drift_min_samples: int = 10

    # Trend engine
    trend_cache_hours: int = 12
    trend_queries_per_request: int = 3  # search.list costs 100 quota units each

    # Authorized caption download needs extra OAuth scope (youtube.force-ssl); off unless you opt in.
    enable_caption_download: bool = False

    analytics_api_base: str = "https://youtubeanalytics.googleapis.com/v2"
    reporting_api_base: str = "https://youtubereporting.googleapis.com/v1"
    google_auth_url: str = "https://accounts.google.com/o/oauth2/v2/auth"
    google_token_url: str = "https://oauth2.googleapis.com/token"

    @property
    def frontend_origin(self) -> str:  # backwards-compatible alias used by CORS
        return self.frontend_url

    @property
    def chat_model(self) -> str:
        return self.groq_chat_model or "llama-3.3-70b-versatile"

    @property
    def transcription_model(self) -> str:
        return self.groq_transcription_model or "whisper-large-v3-turbo"

    @property
    def cookie_secure(self) -> bool:
        return self.frontend_url.startswith("https://")

    @property
    def oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret and self.session_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
