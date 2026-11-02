from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.config import settings
from app.api.db import get_db
from app.api.rate_limit import limiter
from app.api.schemas.auth import AccountInfo, CurrentAccount, LoginRequest, LoginResponse
from app.api.security import create_access_token, get_current_account, verify_password

router = APIRouter(tags=["Auth"])

LOGIN_SQL = text("""
    SELECT account_id, role, customer_id, full_name, email, password_hash, is_active
    FROM user_accounts
    WHERE lower(email) = lower(:email)
""")
LAST_LOGIN_SQL = text("UPDATE user_accounts SET last_login_at = now() WHERE account_id = :account_id")
ME_SQL = text("""
    SELECT account_id, role, customer_id, full_name, email
    FROM user_accounts
    WHERE account_id = :account_id AND is_active
""")


@router.post("/auth/login", response_model=LoginResponse)
@limiter.limit(settings.login_rate_limit)
async def login(request: Request, body: LoginRequest, db: AsyncConnection = Depends(get_db)):
    row = (await db.execute(LOGIN_SQL, {"email": body.email.strip()})).mappings().first()

    # Same answer for an unknown email and a wrong password: nobody learns which emails exist
    if not await verify_password(body.password, row["password_hash"] if row else None):
        raise HTTPException(status_code=401, detail={"reason": "INVALID_CREDENTIALS"})
    if not row["is_active"]:
        raise HTTPException(status_code=403, detail={"reason": "ACCOUNT_DISABLED"})

    await db.execute(LAST_LOGIN_SQL, {"account_id": row["account_id"]})
    await db.commit()

    account = AccountInfo(**{key: row[key] for key in AccountInfo.model_fields})
    token, expires_in = create_access_token(account)
    return LoginResponse(access_token=token, expires_in=expires_in, account=account)


@router.get("/auth/me", response_model=AccountInfo)
async def me(account: CurrentAccount = Depends(get_current_account), db: AsyncConnection = Depends(get_db)):
    row = (await db.execute(ME_SQL, {"account_id": account.account_id})).mappings().first()
    if row is None:
        raise HTTPException(status_code=401, detail={"reason": "ACCOUNT_DISABLED"})
    return AccountInfo(**row)
