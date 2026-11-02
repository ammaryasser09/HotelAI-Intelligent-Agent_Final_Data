from datetime import timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.db import get_db
from app.api.routers.availability import HOTEL_RULES_SQL
from app.api.schemas.admin import DayStats, GroupStats, NewPassword, NewStaff, StaffAccount, Stats, StatsQuery
from app.api.schemas.auth import CurrentAccount
from app.api.security import get_current_admin, hash_password

router = APIRouter(tags=["Admin"])

MAX_DAYS = 366


def refuse(status: int, reason: str, **extra) -> HTTPException:
    return HTTPException(status_code=status, detail={"reason": reason, **extra})


# ---------- statistics ----------

# Every night of the period with the stays that use it. A stay's revenue is spread over its nights
# (amount_due / nights), so a 10-night stay that starts before the period counts only its nights inside it.
NIGHTS_CTE = """
    WITH days AS (
        SELECT d::date AS day FROM generate_series(CAST(:date_from AS date), CAST(:date_to AS date), interval '1 day') d
    ), nights AS (
        SELECT d.day, b.booking_id, b.booking_channel, t.room_type_name, b.amount_due / b.nights AS night_revenue
        FROM days d
        JOIN bookings b ON b.check_in <= d.day AND d.day < b.check_out AND b.booking_status IN ('Confirmed', 'Completed')
        JOIN room_types t ON t.room_type_id = b.room_type_id
    )
"""
ROOMS_SQL = text("SELECT count(*) FROM rooms WHERE status <> 'Maintenance'")
DAILY_SQL = text(NIGHTS_CTE + """
    SELECT d.day, count(n.booking_id) AS rooms_sold, coalesce(sum(n.night_revenue), 0) AS revenue
    FROM days d LEFT JOIN nights n USING (day)
    GROUP BY d.day ORDER BY d.day
""")
BY_CHANNEL_SQL = text(NIGHTS_CTE + """
    SELECT booking_channel AS name, count(*) AS room_nights, sum(night_revenue) AS revenue
    FROM nights GROUP BY booking_channel ORDER BY revenue DESC
""")
BY_ROOM_TYPE_SQL = text(NIGHTS_CTE + """
    SELECT room_type_name AS name, count(*) AS room_nights, sum(night_revenue) AS revenue
    FROM nights GROUP BY room_type_name ORDER BY revenue DESC
""")
BOOKINGS_SQL = text("""
    SELECT (SELECT count(*) FROM bookings
            WHERE created_at::date BETWEEN CAST(:date_from AS date) AND CAST(:date_to AS date)) AS made,
           count(*) FILTER (WHERE booking_status = 'Cancelled') AS cancelled,
           count(*) AS arriving
    FROM bookings WHERE check_in BETWEEN CAST(:date_from AS date) AND CAST(:date_to AS date)
""")
TICKETS_SQL = text("""
    SELECT priority, count(*) AS n FROM customer_requests
    WHERE request_status IN ('Open', 'In Progress') GROUP BY priority
""")
RESOLUTION_SQL = text("""
    SELECT avg(extract(epoch FROM resolved_at - created_at)) / 3600 FROM customer_requests
    WHERE request_status = 'Resolved' AND resolved_at::date BETWEEN CAST(:date_from AS date) AND CAST(:date_to AS date)
""")


def share(part, whole) -> float:
    return round(float(part) / float(whole), 4) if whole else 0.0


@router.get("/admin/stats", response_model=Stats)
async def stats(period: Annotated[StatsQuery, Query()], admin: CurrentAccount = Depends(get_current_admin),
                db: AsyncConnection = Depends(get_db)):
    """Occupancy, revenue (ADR, RevPAR), channels, room types, cancellations and tickets for a period,
    with one row per night for the charts. Default: the 30 days up to the hotel's today."""
    today = (await db.execute(HOTEL_RULES_SQL)).mappings().one()["today"]
    date_to = period.date_to or today
    date_from = period.date_from or date_to - timedelta(days=29)
    if date_to < date_from:
        raise refuse(400, "DATE_TO_BEFORE_DATE_FROM")
    if (date_to - date_from).days + 1 > MAX_DAYS:
        raise refuse(400, "PERIOD_TOO_LONG", max_days=MAX_DAYS)
    dates = {"date_from": date_from, "date_to": date_to}

    rooms = (await db.execute(ROOMS_SQL)).scalar_one()
    daily = (await db.execute(DAILY_SQL, dates)).mappings().all()
    sold = sum(day["rooms_sold"] for day in daily)
    revenue = sum((day["revenue"] for day in daily), Decimal(0))
    available = rooms * len(daily)
    bookings = (await db.execute(BOOKINGS_SQL, dates)).mappings().one()
    resolution = (await db.execute(RESOLUTION_SQL, dates)).scalar_one()

    return Stats(
        date_from=date_from, date_to=date_to, rooms=rooms, room_nights_sold=sold,
        occupancy=share(sold, available),
        revenue=round(float(revenue), 2),
        adr=round(float(revenue) / sold, 2) if sold else 0.0,
        revpar=round(float(revenue) / available, 2) if available else 0.0,
        bookings_made=bookings["made"],
        cancellation_rate=share(bookings["cancelled"], bookings["arriving"]),
        by_channel=[GroupStats(**row) for row in (await db.execute(BY_CHANNEL_SQL, dates)).mappings().all()],
        by_room_type=[GroupStats(**row) for row in (await db.execute(BY_ROOM_TYPE_SQL, dates)).mappings().all()],
        daily=[DayStats(day=day["day"], rooms_sold=day["rooms_sold"], occupancy=share(day["rooms_sold"], rooms),
                        revenue=round(float(day["revenue"]), 2)) for day in daily],
        open_tickets={row["priority"]: row["n"] for row in (await db.execute(TICKETS_SQL)).mappings().all()},
        avg_resolution_hours=round(float(resolution), 1) if resolution is not None else None,
    )


# ---------- staff accounts (staff who forget their password ask the admin) ----------

STAFF_COLUMNS = "account_id, role, full_name, email, is_active, last_login_at"
STAFF_LIST_SQL = text(f"SELECT {STAFF_COLUMNS} FROM user_accounts WHERE role IN ('Staff', 'Admin') ORDER BY role, full_name")
NEW_STAFF_SQL = text(f"""
    INSERT INTO user_accounts (role, full_name, email, password_hash, email_verified)
    VALUES ('Staff', :full_name, lower(:email), :password_hash, true)
    RETURNING {STAFF_COLUMNS}
""")
STAFF_SQL = text(f"SELECT {STAFF_COLUMNS} FROM user_accounts WHERE account_id = :account_id AND role IN ('Staff', 'Admin')")
ACTIVE_SQL = text(f"UPDATE user_accounts SET is_active = :active WHERE account_id = :account_id RETURNING {STAFF_COLUMNS}")
STAFF_PASSWORD_SQL = text("UPDATE user_accounts SET password_hash = :password_hash WHERE account_id = :account_id")


async def staff_member(db: AsyncConnection, account_id: int):
    row = (await db.execute(STAFF_SQL, {"account_id": account_id})).mappings().first()
    if row is None:
        raise refuse(404, "STAFF_NOT_FOUND")
    return row


@router.get("/admin/staff", response_model=list[StaffAccount])
async def list_staff(admin: CurrentAccount = Depends(get_current_admin), db: AsyncConnection = Depends(get_db)):
    return [StaffAccount(**row) for row in (await db.execute(STAFF_LIST_SQL)).mappings().all()]


@router.post("/admin/staff", response_model=StaffAccount, status_code=201)
async def add_staff(body: NewStaff, admin: CurrentAccount = Depends(get_current_admin),
                    db: AsyncConnection = Depends(get_db)):
    try:
        row = (await db.execute(NEW_STAFF_SQL, {"full_name": body.full_name.strip(), "email": body.email.strip(),
                                                "password_hash": await hash_password(body.password)})).mappings().one()
    except IntegrityError:
        raise refuse(409, "EMAIL_ALREADY_REGISTERED")
    await db.commit()
    return StaffAccount(**row)


async def set_active(db: AsyncConnection, admin: CurrentAccount, account_id: int, active: bool) -> StaffAccount:
    await staff_member(db, account_id)
    if account_id == admin.account_id and not active:
        raise refuse(409, "CANNOT_DISABLE_YOURSELF")
    row = (await db.execute(ACTIVE_SQL, {"account_id": account_id, "active": active})).mappings().one()
    await db.commit()
    return StaffAccount(**row)


@router.post("/admin/staff/{account_id}/disable", response_model=StaffAccount)
async def disable_staff(account_id: int, admin: CurrentAccount = Depends(get_current_admin),
                        db: AsyncConnection = Depends(get_db)):
    """The account can no longer log in (a token already given keeps working until it expires, at most 60 min)."""
    return await set_active(db, admin, account_id, False)


@router.post("/admin/staff/{account_id}/enable", response_model=StaffAccount)
async def enable_staff(account_id: int, admin: CurrentAccount = Depends(get_current_admin),
                       db: AsyncConnection = Depends(get_db)):
    return await set_active(db, admin, account_id, True)


@router.post("/admin/staff/{account_id}/password", response_model=StaffAccount)
async def reset_staff_password(account_id: int, body: NewPassword, admin: CurrentAccount = Depends(get_current_admin),
                               db: AsyncConnection = Depends(get_db)):
    row = await staff_member(db, account_id)
    await db.execute(STAFF_PASSWORD_SQL, {"account_id": account_id,
                                          "password_hash": await hash_password(body.new_password)})
    await db.commit()
    return StaffAccount(**row)
