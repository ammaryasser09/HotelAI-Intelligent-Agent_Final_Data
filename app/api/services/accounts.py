import hashlib
import hmac
import secrets
from datetime import date

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.config import settings

# queries.sql 12a: a new code; it works for otp_valid_minutes (10). Only its hash is kept.
CREATE_CODE_SQL = text("""
    INSERT INTO verification_codes (account_id, purpose, code_hash, expires_at)
    VALUES (:account_id, :purpose, :code_hash,
            now() + make_interval(mins => (SELECT value::int FROM app_settings WHERE key = 'otp_valid_minutes')))
    RETURNING (SELECT value::int FROM app_settings WHERE key = 'otp_valid_minutes') AS minutes
""")
# 12b: the latest code that can still be used (not used, not expired, under otp_max_attempts wrong tries)
LATEST_CODE_SQL = text("""
    SELECT code_id, code_hash, attempts,
           (SELECT value::int FROM app_settings WHERE key = 'otp_max_attempts') AS max_attempts
    FROM verification_codes
    WHERE account_id = :account_id AND purpose = :purpose AND used_at IS NULL AND expires_at > now()
      AND attempts < (SELECT value::int FROM app_settings WHERE key = 'otp_max_attempts')
    ORDER BY created_at DESC LIMIT 1
    FOR UPDATE
""")
WRONG_TRY_SQL = text("UPDATE verification_codes SET attempts = attempts + 1 WHERE code_id = :code_id")   # 12c
USED_SQL = text("UPDATE verification_codes SET used_at = now() WHERE code_id = :code_id AND used_at IS NULL")  # 12d


def new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"        # secrets, not random: it cannot be predicted


def hash_code(code: str) -> str:
    # A 6-digit code has only a million values, so a plain hash could be reversed by trying them all.
    # Mixing in our secret (HMAC) means a stolen database alone is not enough.
    return hmac.new(settings.jwt_secret.encode(), code.encode(), hashlib.sha256).hexdigest()


async def create_code(db: AsyncConnection, account_id: int, purpose: str) -> tuple[str, int]:
    """A new code for the account (saved as a hash; the caller commits and emails the plain code)."""
    code = new_code()
    minutes = (await db.execute(CREATE_CODE_SQL, {
        "account_id": account_id, "purpose": purpose, "code_hash": hash_code(code),
    })).scalar_one()
    return code, minutes


async def use_code(db: AsyncConnection, account_id: int, purpose: str, typed: str) -> None:
    """Checks the code the guest typed. A right code is used up; a wrong one counts as a try.
    Raises 400 with the reason; the caller commits either way (a wrong try must be saved)."""
    latest = (await db.execute(LATEST_CODE_SQL, {"account_id": account_id, "purpose": purpose})).mappings().first()
    if latest is None:
        raise HTTPException(status_code=400, detail={"reason": "CODE_EXPIRED"})    # ask for a new one
    if not hmac.compare_digest(latest["code_hash"], hash_code(typed)):
        await db.execute(WRONG_TRY_SQL, {"code_id": latest["code_id"]})
        await db.commit()
        raise HTTPException(status_code=400, detail={
            "reason": "WRONG_CODE", "attempts_left": latest["max_attempts"] - latest["attempts"] - 1})
    await db.execute(USED_SQL, {"code_id": latest["code_id"]})


def age_on(born: date, day: date) -> int:
    return day.year - born.year - ((day.month, day.day) < (born.month, born.day))


def check_age(born: date, today: date) -> None:
    if age_on(born, today) < settings.min_guest_age:
        raise HTTPException(status_code=400, detail={"reason": "TOO_YOUNG", "min_age": settings.min_guest_age})
