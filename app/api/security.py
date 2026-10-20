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


def create_access_token(account: AccountInfo) -> tuple[str, int]:
    expires_in = settings.access_token_minutes * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(account.account_id),
        "role": account.role,
        "customer_id": account.customer_id,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM), expires_in


def _unauthorized(reason: str) -> HTTPException:
    return HTTPException(status_code=401, detail={"reason": reason}, headers={"WWW-Authenticate": "Bearer"})


def _read_token(credentials: HTTPAuthorizationCredentials) -> CurrentAccount:
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise _unauthorized("TOKEN_EXPIRED")
    except jwt.InvalidTokenError:
        raise _unauthorized("INVALID_TOKEN")
    return CurrentAccount(
        account_id=int(payload["sub"]),
        role=payload["role"],
        customer_id=payload.get("customer_id"),
    )


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
    return account
