from decimal import Decimal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Requests one client (IP address) may send; change it in .env with RATE_LIMIT=...
    rate_limit: str = "60/minute"

    # Business rules that are not stored in the database (docs/BUSINESS_RULES.md)
    long_stay_min_nights: int = 7
    non_refundable_multiplier: Decimal = Decimal("0.85")


settings = Settings()
