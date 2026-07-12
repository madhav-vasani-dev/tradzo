"""Central configuration loaded from environment (.env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:4200"
    frontend_base_url: str = "http://localhost:4200"

    # Upstox OAuth — bring-your-own-key (BYOK).
    # Each user registers their own Upstox app whose redirect URI must equal
    # `upstox_redirect_uri` below; they supply their own key/secret at connect
    # time. The *_client_id/secret here are an optional platform-wide fallback.
    upstox_client_id: str = ""
    upstox_client_secret: str = ""
    upstox_redirect_uri: str = "http://localhost:8000/broker/upstox/callback"

    # Jainam — Symphony XTS Retail API.
    # `jtrade.jainam.in:5000` is Jainam's XTS Retail host; override per environment.
    jainam_xts_base_url: str = "https://jtrade.jainam.in:5000"
    # XTS login "source": WebAPI for retail, WEBAPI/DEALERAPI variants exist.
    jainam_xts_source: str = "WebAPI"

    # Firebase
    firebase_credentials_path: str = "./firebase-service-account.json"

    # Token encryption
    token_encryption_key: str = ""

    # Scheduler
    enable_scheduler: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()

# Indian market timezone — used by the scheduler and expiry calculations.
IST = "Asia/Kolkata"
