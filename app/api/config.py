from decimal import Decimal
from typing import Literal

from pydantic import model_validator
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
    paymob_intention_url: str = "https://accept.paymob.com/v1/intention/"
    paymob_checkout_url: str = "https://eg.checkout.paymob.com/"
    paymob_auth_url: str = "https://accept.paymob.com/api/auth/tokens"
    paymob_refund_url: str = "https://accept.paymob.com/api/acceptance/void_refund/refund"

    # The address Paymob can reach this API at (the ngrok link while it runs on a laptop)
    public_base_url: str | None = None

    # Business rules that are not stored in the database (docs/BUSINESS_RULES.md)
    # Emails to guests: log = written to logs/emails/ (default), smtp = really sent
    email_provider: Literal["log", "smtp"] = "log"
    email_from: str = "Nile Pearl Hotel <reservations@nilepearl.example>"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None

    # How often unpaid bookings are checked and cancelled once their hold is over (0 = never)
    expiry_check_seconds: int = 300

    long_stay_min_nights: int = 7
    non_refundable_multiplier: Decimal = Decimal("0.85")

    @model_validator(mode="after")
    def paymob_needs_its_keys(self):
        if self.payment_provider == "paymob":
            needed = {
                "PAYMOB_API_KEY": self.paymob_api_key,
                "PAYMOB_SECRET_KEY": self.paymob_secret_key,
                "PAYMOB_PUBLIC_KEY": self.paymob_public_key,
                "PAYMOB_HMAC_SECRET": self.paymob_hmac_secret,
                "PAYMOB_INTEGRATION_ID": self.paymob_integration_id,
                "PUBLIC_BASE_URL": self.public_base_url,
            }
            missing = [name for name, value in needed.items() if not value]
            if missing:
                raise ValueError(f"PAYMENT_PROVIDER=paymob needs these in .env: {', '.join(missing)}")
        if self.email_provider == "smtp":
            missing = [name for name, value in {"SMTP_HOST": self.smtp_host, "SMTP_USER": self.smtp_user,
                                                "SMTP_PASSWORD": self.smtp_password}.items() if not value]
            if missing:
                raise ValueError(f"EMAIL_PROVIDER=smtp needs these in .env: {', '.join(missing)}")
        return self


settings = Settings()
