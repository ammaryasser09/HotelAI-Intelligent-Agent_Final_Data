from decimal import Decimal
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", env_ignore_empty=True
    )

    database_url: str
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Requests one client (IP address) may send; change them in .env, e.g. RATE_LIMIT=100/minute
    rate_limit: str = "60/minute"
    login_rate_limit: str = "5/minute"
    link_rate_limit: str = "10/minute"

    # Login tokens (JWT). JWT_SECRET must be set in .env and never shared or committed.
    jwt_secret: str
    access_token_minutes: int = 60

    # Payments: "mock" = the fake Paymob built into the API (no keys needed), "paymob" = Paymob test mode
    payment_provider: Literal["mock", "paymob"] = "mock"

    # Paymob payment gateway (test mode). Only used when PAYMENT_PROVIDER=paymob.
    paymob_api_key: str | None = None
    paymob_public_key: str | None = None
    paymob_secret_key: str | None = None
    paymob_hmac_secret: str | None = None
    paymob_integration_id: int | None = None

    # Business rules that are not stored in the database (docs/BUSINESS_RULES.md)
    long_stay_min_nights: int = 7
    non_refundable_multiplier: Decimal = Decimal("0.85")


settings = Settings()
