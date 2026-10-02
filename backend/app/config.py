from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

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

    analytics_api_base: str = "https://youtubeanalytics.googleapis.com/v2"
    reporting_api_base: str = "https://youtubereporting.googleapis.com/v1"
    google_auth_url: str = "https://accounts.google.com/o/oauth2/v2/auth"
    google_token_url: str = "https://oauth2.googleapis.com/token"

    @property
    def frontend_origin(self) -> str:  # backwards-compatible alias used by CORS
        return self.frontend_url

    @property
    def cookie_secure(self) -> bool:
        return self.frontend_url.startswith("https://")

    @property
    def oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret and self.session_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
