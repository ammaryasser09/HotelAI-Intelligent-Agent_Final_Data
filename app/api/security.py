from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.config import settings
from app.api.schemas.auth import AccountInfo, CurrentAccount

ALGORITHM = "HS256"

# Adds the "Authorize" button to /docs; auto_error=False lets us send our own 401 answer
bearer = HTTPBearer(auto_error=False)

# Checked when the email does not exist, so a wrong email takes as long as a wrong password
_DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt(rounds=10))


async def verify_password(password: str, password_hash: str | None) -> bool:
    hashed = password_hash.encode() if password_hash else _DUMMY_HASH
    # bcrypt is slow on purpose (~0.1 s): run it in a thread so the server keeps serving others
    matches = await run_in_threadpool(bcrypt.checkpw, password.encode()[:72], hashed)
    return matches and password_hash is not None


async def hash_password(password: str) -> str:
    hashed = await run_in_threadpool(bcrypt.hashpw, password.encode()[:72], bcrypt.gensalt())
    return hashed.decode()


def create_access_token(account: AccountInfo) -> tuple[str, int]:
    expires_in = settings.access_token_minutes * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(account.account_id),
        "role": account.role,
        "customer_id": account.customer_id,
        "email_verified": account.email_verified,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM), expires_in


def _unauthorized(reason: str) -> HTTPException:
    return HTTPException(status_code=401, detail={"reason": reason}, headers={"WWW-Authenticate": "Bearer"})


def read_access_token(token: str) -> CurrentAccount:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise _unauthorized("TOKEN_EXPIRED")
    except jwt.InvalidTokenError:
        raise _unauthorized("INVALID_TOKEN")
    if "role" not in payload:          # e.g. a live-chat token: it only opens its own chat
        raise _unauthorized("INVALID_TOKEN")
    return CurrentAccount(
        account_id=int(payload["sub"]),
        role=payload["role"],
        customer_id=payload.get("customer_id"),
        email_verified=payload.get("email_verified", False),
    )


def _read_token(credentials: HTTPAuthorizationCredentials) -> CurrentAccount:
    return read_access_token(credentials.credentials)


CHAT_TOKEN_HOURS = 3


def create_chat_token(call_id) -> str:
    """Opens the live chat of one call only (a visitor in a chat has no login of their own)."""
    now = datetime.now(timezone.utc)
    payload = {"chat": str(call_id), "iat": now, "exp": now + timedelta(hours=CHAT_TOKEN_HOURS)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def read_chat_token(token: str) -> str | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM]).get("chat")
    except jwt.InvalidTokenError:
        return None


async def get_current_account(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> CurrentAccount:
    """For endpoints that need a login: 401 without a valid token."""
    if credentials is None:
        raise _unauthorized("NOT_LOGGED_IN")
    return _read_token(credentials)


async def get_optional_account(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> CurrentAccount | None:
    """For endpoints a visitor can use too: None without a token."""
    return None if credentials is None else _read_token(credentials)


async def get_current_guest(account: CurrentAccount = Depends(get_current_account)) -> CurrentAccount:
    if account.role != "Guest":
        raise HTTPException(status_code=403, detail={"reason": "GUESTS_ONLY"})
    if not account.email_verified:
        # a new account sees and makes bookings only after proving the email is theirs
        raise HTTPException(status_code=403, detail={"reason": "EMAIL_NOT_VERIFIED"})
    return account


async def get_current_staff(account: CurrentAccount = Depends(get_current_account)) -> CurrentAccount:
    """The staff dashboard: Staff and Admin."""
    if account.role not in ("Staff", "Admin"):
        raise HTTPException(status_code=403, detail={"reason": "STAFF_ONLY"})
    return account


async def get_current_admin(account: CurrentAccount = Depends(get_current_account)) -> CurrentAccount:
    if account.role != "Admin":
        raise HTTPException(status_code=403, detail={"reason": "ADMIN_ONLY"})
    return account
