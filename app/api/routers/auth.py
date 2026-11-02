from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.config import settings
from app.api.db import get_db
from app.api.rate_limit import limiter
from app.api.routers.availability import HOTEL_RULES_SQL
from app.api.schemas.auth import (AccountInfo, CodeRequest, CodeSent, CurrentAccount, ForgotPasswordRequest,
                                  LoginRequest, LoginResponse, ResetPasswordRequest, SignupRequest)
from app.api.security import create_access_token, get_current_account, hash_password, verify_password
from app.api.services.accounts import check_age, create_code, use_code
from app.api.services.email import send_code

router = APIRouter(tags=["Auth"])

LOGIN_SQL = text("""
    SELECT account_id, role, customer_id, full_name, email, email_verified, password_hash, is_active
    FROM user_accounts
    WHERE lower(email) = lower(:email)
""")
LAST_LOGIN_SQL = text("UPDATE user_accounts SET last_login_at = now() WHERE account_id = :account_id")
ME_SQL = text("""
    SELECT account_id, role, customer_id, full_name, email, email_verified
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



# ---------- sign up and email codes (queries.sql 12) ----------

# Is the email already a guest of the hotel (a booking by phone, an agency...) and does it have an account?
CUSTOMER_BY_EMAIL_SQL = text("""
    SELECT c.customer_id, c.first_name, c.date_of_birth, c.nationality,
           EXISTS (SELECT 1 FROM user_accounts a WHERE a.customer_id = c.customer_id) AS has_account
    FROM customers c WHERE lower(c.email) = lower(:email)
""")
ACCOUNT_EMAIL_TAKEN_SQL = text("SELECT 1 FROM user_accounts WHERE lower(email) = lower(:email)")
PHONE_TAKEN_SQL = text("SELECT 1 FROM customers WHERE phone = :phone")
NEW_CUSTOMER_SQL = text("""
    INSERT INTO customers (first_name, last_name, email, phone, nationality, date_of_birth)
    VALUES (:first_name, :last_name, lower(:email), :phone, :nationality, :date_of_birth)
    RETURNING customer_id
""")
FILL_CUSTOMER_SQL = text("""
    UPDATE customers SET nationality = coalesce(nationality, :nationality),
                         date_of_birth = coalesce(date_of_birth, :date_of_birth)
    WHERE customer_id = :customer_id
""")
NEW_ACCOUNT_SQL = text("""
    INSERT INTO user_accounts (role, customer_id, full_name, email, password_hash, email_verified)
    VALUES ('Guest', :customer_id, :full_name, lower(:email), :password_hash, false)
    RETURNING account_id, role, customer_id, full_name, email, email_verified
""")
ACCOUNT_SQL = text("""
    SELECT a.account_id, a.role, a.customer_id, a.full_name, a.email, a.email_verified, a.is_active,
           coalesce(c.first_name, a.full_name) AS first_name
    FROM user_accounts a LEFT JOIN customers c USING (customer_id)
    WHERE a.account_id = :account_id OR (CAST(:email AS text) IS NOT NULL AND lower(a.email) = lower(CAST(:email AS text)))
""")
VERIFIED_SQL = text("UPDATE user_accounts SET email_verified = true WHERE account_id = :account_id")
NEW_PASSWORD_SQL = text("UPDATE user_accounts SET password_hash = :password_hash WHERE account_id = :account_id")


def logged_in(row) -> LoginResponse:
    account = AccountInfo(**{key: row[key] for key in AccountInfo.model_fields})
    token, expires_in = create_access_token(account)
    return LoginResponse(access_token=token, expires_in=expires_in, account=account)


async def find_account(db: AsyncConnection, account_id: int | None = None, email: str | None = None):
    return (await db.execute(ACCOUNT_SQL, {"account_id": account_id or 0, "email": email})).mappings().first()


@router.post("/auth/signup", response_model=LoginResponse, status_code=201)
@limiter.limit(settings.signup_rate_limit)
async def signup(request: Request, body: SignupRequest, background: BackgroundTasks,
                 db: AsyncConnection = Depends(get_db)):
    """A new guest account. The guest is logged in at once and gets a code by email to confirm it;
    bookings open after the email is confirmed (POST /auth/verify-email)."""
    if body.date_of_birth:
        check_age(body.date_of_birth, (await db.execute(HOTEL_RULES_SQL)).mappings().one()["today"])
    if (await db.execute(ACCOUNT_EMAIL_TAKEN_SQL, {"email": body.email})).first():
        raise HTTPException(status_code=409, detail={"reason": "EMAIL_ALREADY_REGISTERED"})

    customer = (await db.execute(CUSTOMER_BY_EMAIL_SQL, {"email": body.email})).mappings().first()
    if customer and customer["has_account"]:
        raise HTTPException(status_code=409, detail={"reason": "EMAIL_ALREADY_REGISTERED"})
    if customer:
        # already a guest of the hotel without an account: the account joins the same guest, so after
        # confirming the email they see their bookings
        customer_id = customer["customer_id"]
        await db.execute(FILL_CUSTOMER_SQL, {"customer_id": customer_id, "nationality": body.nationality,
                                             "date_of_birth": body.date_of_birth})
    else:
        if (await db.execute(PHONE_TAKEN_SQL, {"phone": body.phone})).first():
            raise HTTPException(status_code=409, detail={"reason": "PHONE_ALREADY_REGISTERED"})

        try:
            customer_id = (await db.execute(NEW_CUSTOMER_SQL, body.model_dump(exclude={"password"}))).scalar_one()
        except IntegrityError:   # the same email or phone signed up a moment ago in another request
            raise HTTPException(status_code=409, detail={"reason": "ALREADY_REGISTERED"})

    try:
        row = (await db.execute(NEW_ACCOUNT_SQL, {
            "customer_id": customer_id, "full_name": f"{body.first_name} {body.last_name}",
            "email": body.email, "password_hash": await hash_password(body.password),
        })).mappings().one()
    except IntegrityError:
        raise HTTPException(status_code=409, detail={"reason": "ALREADY_REGISTERED"})
    code, minutes = await create_code(db, row["account_id"], "verify_email")
    await db.commit()

    background.add_task(send_code, row["email"], body.first_name, code, "verify_email", minutes)
    return logged_in(row)


@router.post("/auth/verify-email", response_model=LoginResponse)
@limiter.limit(settings.code_rate_limit)
async def verify_email(request: Request, body: CodeRequest, account: CurrentAccount = Depends(get_current_account),
                       db: AsyncConnection = Depends(get_db)):
    """The code from the email. Answers with a new login token that opens bookings."""
    row = await find_account(db, account_id=account.account_id)
    if row["email_verified"]:
        raise HTTPException(status_code=409, detail={"reason": "ALREADY_VERIFIED"})
    await use_code(db, account.account_id, "verify_email", body.code)
    await db.execute(VERIFIED_SQL, {"account_id": account.account_id})
    await db.commit()
    return logged_in({**row, "email_verified": True})


@router.post("/auth/verify-email/resend", response_model=CodeSent)
@limiter.limit(settings.code_rate_limit)
async def resend_code(request: Request, background: BackgroundTasks,
                      account: CurrentAccount = Depends(get_current_account), db: AsyncConnection = Depends(get_db)):
    row = await find_account(db, account_id=account.account_id)
    if row["email_verified"]:
        raise HTTPException(status_code=409, detail={"reason": "ALREADY_VERIFIED"})
    code, minutes = await create_code(db, account.account_id, "verify_email")
    await db.commit()
    background.add_task(send_code, row["email"], row["first_name"], code, "verify_email", minutes)
    return CodeSent(expires_in_minutes=minutes)


@router.post("/auth/forgot-password", response_model=CodeSent)
@limiter.limit(settings.code_rate_limit)
async def forgot_password(request: Request, body: ForgotPasswordRequest, background: BackgroundTasks,
                          db: AsyncConnection = Depends(get_db)):
    """Emails a reset code to a guest. The answer is the same whether the email exists or not, so nobody
    can use this to find out who has an account. Staff and admins ask the hotel administration instead."""
    row = await find_account(db, email=body.email)
    minutes = 10
    if row and row["role"] == "Guest" and row["is_active"]:
        code, minutes = await create_code(db, row["account_id"], "reset_password")
        await db.commit()
        background.add_task(send_code, row["email"], row["first_name"], code, "reset_password", minutes)
    return CodeSent(expires_in_minutes=minutes)


@router.post("/auth/reset-password", response_model=LoginResponse)
@limiter.limit(settings.code_rate_limit)
async def reset_password(request: Request, body: ResetPasswordRequest, db: AsyncConnection = Depends(get_db)):
    """The code from the email + the new password. The guest is logged in with the new password."""
    row = await find_account(db, email=body.email)
    if row is None or row["role"] != "Guest" or not row["is_active"]:
        raise HTTPException(status_code=400, detail={"reason": "CODE_EXPIRED"})   # same as a stale code
    await use_code(db, row["account_id"], "reset_password", body.code)
    await db.execute(NEW_PASSWORD_SQL, {"account_id": row["account_id"],
                                        "password_hash": await hash_password(body.new_password)})
    # the code reached their inbox, so the email is theirs
    await db.execute(VERIFIED_SQL, {"account_id": row["account_id"]})
    await db.commit()
    return logged_in({**row, "email_verified": True})
