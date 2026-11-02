from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.config import settings
from app.api.db import get_db
from app.api.rate_limit import limiter
from app.api.schemas.auth import CurrentAccount
from app.api.schemas.requests import (COMPLAINT_CATEGORIES, SPECIAL_REQUEST_CATEGORIES, EmergencyOpened,
                                      EmergencyRequest, LoyaltyStatus, NewRequest, RequestOut)
from app.api.security import get_current_guest, get_optional_account

router = APIRouter(tags=["Requests"])

REQUEST_COLUMNS = """r.request_id, r.call_id, r.request_type, r.category, r.priority, r.request_status, r.request_text,
                     r.booking_id, r.decision, d.discount_code, r.created_at, r.resolved_at"""

# queries.sql 10: a request becomes a ticket for the staff. Emergency = Critical, Staff Callback = Urgent.
NEW_REQUEST_SQL = text(f"""
    WITH r AS (
        INSERT INTO customer_requests (customer_id, booking_id, call_id, request_type, category, request_text, priority)
        VALUES (:customer_id, upper(:booking_id), :call_id, :request_type, :category, :request_text, :priority)
        RETURNING *)
    SELECT {REQUEST_COLUMNS} FROM r LEFT JOIN discount_codes d ON d.code_id = r.issued_code_id
""")
MY_REQUESTS_SQL = text(f"""
    SELECT {REQUEST_COLUMNS}
    FROM customer_requests r LEFT JOIN discount_codes d ON d.code_id = r.issued_code_id
    WHERE r.customer_id = :customer_id
    ORDER BY r.created_at DESC
""")
BOOKING_OF_ACCOUNT_SQL = text("""
    SELECT 1 FROM v_account_bookings WHERE account_id = :account_id AND booking_id = upper(:booking_id)
""")
CALL_EXISTS_SQL = text("SELECT 1 FROM calls WHERE call_id = :call_id")
# an emergency from the website, with no call behind it: it gets its own record so staff can follow it up
WEB_EMERGENCY_CALL_SQL = text("""
    INSERT INTO calls (channel, account_id, customer_id, status, escalation_reason)
    VALUES ('text', :account_id, :customer_id, 'escalated', 'Emergency raised from the website')
    RETURNING call_id
""")
RECEPTION_SQL = text("SELECT value FROM app_settings WHERE key = 'reception_phone'")

# queries.sql 5: tier, points and what they are worth, late check-out
LOYALTY_SQL = text("""
    SELECT m.tier, m.points_balance, m.total_stays, t.benefits, to_char(t.late_checkout_until, 'HH24:MI') AS late_checkout_until,
           floor(m.points_balance / r1.value) * r2.value AS points_worth_egp
    FROM loyalty_members m
    JOIN loyalty_tiers t ON t.tier = m.tier
    CROSS JOIN (SELECT value FROM loyalty_rules WHERE rule = 'redeem_points') r1
    CROSS JOIN (SELECT value FROM loyalty_rules WHERE rule = 'redeem_value') r2
    WHERE m.customer_id = :customer_id AND m.status = 'Active'
""")


def priority_of(request_type: str) -> str:
    return {"Emergency": "Critical", "Staff Callback": "Urgent"}.get(request_type, "Normal")


def refuse(status: int, reason: str, **extra) -> HTTPException:
    return HTTPException(status_code=status, detail={"reason": reason, **extra})


async def check_call(db: AsyncConnection, call_id) -> None:
    if call_id and not (await db.execute(CALL_EXISTS_SQL, {"call_id": call_id})).first():
        raise refuse(404, "CALL_NOT_FOUND")


def check_category(body: NewRequest) -> None:
    """The same rules the database keeps, answered with a clear reason instead of a database error."""
    if body.request_type == "Special Request":
        if body.booking_id is None:
            raise refuse(400, "BOOKING_REQUIRED")
        if body.category not in SPECIAL_REQUEST_CATEGORIES:
            raise refuse(400, "WRONG_CATEGORY", categories=list(SPECIAL_REQUEST_CATEGORIES))
    elif body.request_type == "Complaint":
        if body.category is not None and body.category not in COMPLAINT_CATEGORIES:
            raise refuse(400, "WRONG_CATEGORY", categories=list(COMPLAINT_CATEGORIES))
    elif body.category is not None:
        raise refuse(400, "NO_CATEGORY_FOR_THIS_TYPE")


@router.post("/requests", response_model=RequestOut, status_code=201)
async def create_request(body: NewRequest, guest: CurrentAccount = Depends(get_current_guest),
                         db: AsyncConnection = Depends(get_db)):
    """A logged-in guest asks for something (housekeeping, maintenance, a complaint, a discount...).
    It becomes a ticket on the staff dashboard. Nour never grants discounts: a Discount Request waits for the admin."""
    check_category(body)
    if body.booking_id and not (await db.execute(BOOKING_OF_ACCOUNT_SQL, {
            "account_id": guest.account_id, "booking_id": body.booking_id})).first():
        raise refuse(404, "BOOKING_NOT_FOUND")
    await check_call(db, body.call_id)
    row = (await db.execute(NEW_REQUEST_SQL, {**body.model_dump(), "customer_id": guest.customer_id,
                                              "priority": priority_of(body.request_type)})).mappings().one()
    await db.commit()
    return RequestOut(**row)


@router.post("/requests/emergency", response_model=EmergencyOpened, status_code=201)
@limiter.limit(settings.link_rate_limit)
async def emergency(request: Request, body: EmergencyRequest,
                    account: CurrentAccount | None = Depends(get_optional_account),
                    db: AsyncConnection = Depends(get_db)):
    """Anyone can raise an emergency, logged in or not. It opens a Critical ticket at the top of the staff queue
    and answers with the emergency numbers to call right away."""
    customer_id = account.customer_id if account and account.role == "Guest" else None
    await check_call(db, body.call_id)
    call_id = body.call_id or (await db.execute(WEB_EMERGENCY_CALL_SQL, {
        "account_id": account.account_id if account else None, "customer_id": customer_id})).scalar_one()
    row = (await db.execute(NEW_REQUEST_SQL, {
        "customer_id": customer_id, "booking_id": None, "category": None, "request_type": "Emergency",
        "priority": "Critical",
        "call_id": call_id,
        "request_text": body.request_text,
    })).mappings().one()
    reception = (await db.execute(RECEPTION_SQL)).scalar_one()
    await db.commit()
    return EmergencyOpened(request=RequestOut(**row), reception=reception)


@router.get("/me/requests", response_model=list[RequestOut])
async def my_requests(guest: CurrentAccount = Depends(get_current_guest), db: AsyncConnection = Depends(get_db)):
    rows = (await db.execute(MY_REQUESTS_SQL, {"customer_id": guest.customer_id})).mappings().all()
    return [RequestOut(**row) for row in rows]


@router.get("/me/loyalty", response_model=LoyaltyStatus)
async def my_loyalty(guest: CurrentAccount = Depends(get_current_guest), db: AsyncConnection = Depends(get_db)):
    """Nile Pearl Rewards: tier, points (and what they are worth), and the free late check-out of the tier."""
    row = (await db.execute(LOYALTY_SQL, {"customer_id": guest.customer_id})).mappings().first()
    if row is None:
        return LoyaltyStatus(member=False)
    return LoyaltyStatus(member=True, **row)
