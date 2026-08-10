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

    # Delta Exchange — Indian endpoint for BTC option strategies.
    delta_exchange_base_url: str = "https://api.india.delta.exchange/v2"
    # USD → INR conversion rate used for BTC option PnL display.
    usd_to_inr_rate: float = 85.0

    # Firebase
    firebase_credentials_path: str = "./firebase-service-account.json"

    # Token encryption
    token_encryption_key: str = ""

    # Scheduler
    enable_scheduler: bool = True
    # Seconds before the strategy entry time that the pre-stage job runs. Everything
    # slow (Firestore reads, token decryption, instrument resolution, market data) is
    # done during this window so the SELL orders can fire exactly at the entry second.
    entry_prestage_lead_seconds: int = 15
    # How long before T0 the market snapshot is taken. Must be < entry_prestage_lead_seconds,
    # and large enough to cover the option-chain fetch plus any broker instrument lookups.
    entry_marketdata_lead_seconds: int = 6

    # Orders
    # Product code for equity/F&O legs. "delivery" = Upstox "D" / Jainam "NRML" (carry
    # forward, no broker auto-square-off at 15:15). "intraday" = Upstox "I" / Jainam "MIS".
    equity_product: str = "delivery"
    # NSE discontinued SL-M in the F&O segment, so brokers silently downgrade an SL-M to
    # a stop-LIMIT priced at the trigger — which does not fill through a gap. When that
    # happens we repair the order to a stop-limit whose limit price sits this far past the
    # trigger, so it still fills on a spike with a bounded worst price.
    sl_limit_buffer_pct: float = 10.0

    # Live market data feed (websocket) — drives live mark-to-market P&L on open positions.
    enable_live_feed: bool = True
    # How often the in-memory LTP cache is flushed to Firestore position docs.
    live_pnl_write_interval_seconds: float = 5.0

    # Google Drive — used by seasonality analysis to store/retrieve 1-min OHLCV CSVs.
    # Share the Drive folder with the service-account email for write access.
    gdrive_service_account_path: str = "./gdrive-service-account.json"
    gdrive_folder_id: str = ""  # Drive folder ID (from the folder's URL)
    google_api_key: str = ""  # Optional Google API Key for Drive API v3 bulk folder pagination

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
