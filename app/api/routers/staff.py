import secrets
import string

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.db import get_db
from app.api.schemas.auth import CurrentAccount
from app.api.schemas.staff import (ApproveDiscount, CheckOutRequest, CloseTicket, DeskBooking, DeskResult,
                                   DiscountDecision, DiscountRequestOut, Ticket, TicketDecision)
from app.api.security import get_current_admin, get_current_staff
from app.api.services.email import send_discount_decision

router = APIRouter(tags=["Staff dashboard"])


def refuse(status: int, reason: str, **extra) -> HTTPException:
    return HTTPException(status_code=status, detail={"reason": reason, **extra})


# ---------- front desk (queries.sql 8) ----------

DESK_COLUMNS = """booking_id, first_name, last_name, room_type_name, room_number, check_in, check_out, nights,
                  adults, children, amount_due, coalesce(amount_paid, 0) - coalesce(refund_amount, 0) AS amount_paid,
                  amount_due - (coalesce(amount_paid, 0) - coalesce(refund_amount, 0)) AS balance_due, checked_in_at"""
# 8a: confirmed stays arriving today (or late) that have not checked in yet
ARRIVALS_SQL = text(f"""
    SELECT {DESK_COLUMNS} FROM v_booking_details
    WHERE booking_status = 'Confirmed' AND check_in <= hotel_today() AND checked_in_at IS NULL
    ORDER BY room_number
""")
# guests in the hotel now, those leaving first
IN_HOUSE_SQL = text(f"""
    SELECT {DESK_COLUMNS} FROM v_booking_details
    WHERE booking_status = 'Confirmed' AND checked_in_at IS NOT NULL
    ORDER BY check_out, room_number
""")
DESK_STATE_SQL = text("""
    SELECT b.booking_id, b.booking_status, b.room_number, b.checked_in_at, b.check_in > hotel_today() AS arrives_later,
           b.amount_due - (p.amount_paid - p.refund_amount) AS balance_due
    FROM bookings b JOIN payments p USING (booking_id)
    WHERE b.booking_id = upper(:booking_id)
    FOR UPDATE OF b, p
""")
CHECK_IN_SQL = text("UPDATE bookings SET checked_in_at = now() WHERE booking_id = :booking_id")
ROOM_STATUS_SQL = text("UPDATE rooms SET status = :status WHERE room_number = :room_number")
# 8c: the balance is paid at the desk, the stay is completed and the room freed
BALANCE_SQL = text("""
    UPDATE payments p
    SET amount_paid = b.amount_due + p.refund_amount, payment_status = 'Paid', payment_method = :payment_method
    FROM bookings b
    WHERE b.booking_id = p.booking_id AND b.booking_id = :booking_id
""")
CHECK_OUT_SQL = text("""
    UPDATE bookings SET booking_status = 'Completed', checked_out_at = now() WHERE booking_id = :booking_id
""")


async def desk_state(db: AsyncConnection, booking_id: str):
    state = (await db.execute(DESK_STATE_SQL, {"booking_id": booking_id})).mappings().first()
    if state is None:
        raise refuse(404, "BOOKING_NOT_FOUND")
    if state["booking_status"] != "Confirmed":
        raise refuse(409, "NOT_CONFIRMED", booking_status=state["booking_status"])
    return state


@router.get("/staff/arrivals", response_model=list[DeskBooking])
async def arrivals(staff: CurrentAccount = Depends(get_current_staff), db: AsyncConnection = Depends(get_db)):
    return [DeskBooking(**row) for row in (await db.execute(ARRIVALS_SQL)).mappings().all()]


@router.get("/staff/in-house", response_model=list[DeskBooking])
async def in_house(staff: CurrentAccount = Depends(get_current_staff), db: AsyncConnection = Depends(get_db)):
    return [DeskBooking(**row) for row in (await db.execute(IN_HOUSE_SQL)).mappings().all()]


@router.post("/staff/bookings/{booking_id}/check-in", response_model=DeskResult)
async def check_in(booking_id: str, staff: CurrentAccount = Depends(get_current_staff),
                   db: AsyncConnection = Depends(get_db)):
    state = await desk_state(db, booking_id)
    if state["checked_in_at"]:
        raise refuse(409, "ALREADY_CHECKED_IN")
    if state["arrives_later"]:
        raise refuse(409, "NOT_ARRIVAL_DAY_YET")
    await db.execute(CHECK_IN_SQL, {"booking_id": state["booking_id"]})
    await db.execute(ROOM_STATUS_SQL, {"status": "Occupied", "room_number": state["room_number"]})
    await db.commit()
    return DeskResult(booking_id=state["booking_id"], booking_status="Confirmed", room_number=state["room_number"])


@router.post("/staff/bookings/{booking_id}/check-out", response_model=DeskResult)
async def check_out(booking_id: str, body: CheckOutRequest, staff: CurrentAccount = Depends(get_current_staff),
                    db: AsyncConnection = Depends(get_db)):
    """The guest pays what is left (the deposit was paid online) and leaves; the room is free again."""
    state = await desk_state(db, booking_id)
    if not state["checked_in_at"]:
        raise refuse(409, "NOT_CHECKED_IN")
    await db.execute(BALANCE_SQL, {"booking_id": state["booking_id"], "payment_method": body.payment_method})
    await db.execute(CHECK_OUT_SQL, {"booking_id": state["booking_id"]})
    await db.execute(ROOM_STATUS_SQL, {"status": "Available", "room_number": state["room_number"]})
    await db.commit()
    return DeskResult(booking_id=state["booking_id"], booking_status="Completed", room_number=state["room_number"],
                      balance_paid=float(state["balance_due"]))


# ---------- tickets (queries.sql 10b, 10d, 10e, 10f) ----------

TICKET_COLUMNS = """r.request_id, r.priority, r.request_type, r.category, r.request_status, r.request_text,
                    r.customer_id, c.first_name || ' ' || c.last_name AS guest_name, r.booking_id, b.room_number,
                    r.call_id, h.full_name AS handled_by, r.decision, r.created_at"""
TICKET_JOINS = """customer_requests r
                  LEFT JOIN customers c ON c.customer_id = r.customer_id
                  LEFT JOIN bookings b ON b.booking_id = r.booking_id
                  LEFT JOIN user_accounts h ON h.account_id = r.handled_by"""
# 10b: open tickets, emergencies first
QUEUE_SQL = text(f"""
    SELECT {TICKET_COLUMNS} FROM {TICKET_JOINS}
    WHERE r.request_status IN ('Open', 'In Progress')
    ORDER BY CASE r.priority WHEN 'Critical' THEN 0 WHEN 'Urgent' THEN 1 ELSE 2 END, r.created_at
""")
TICKET_SQL = text(f"SELECT {TICKET_COLUMNS} FROM {TICKET_JOINS} WHERE r.request_id = upper(:request_id)")
TICKET_STATE_SQL = text("""
    SELECT request_id, request_type, request_status, decision FROM customer_requests
    WHERE request_id = upper(:request_id) FOR UPDATE
""")
TAKE_SQL = text("""
    UPDATE customer_requests SET request_status = 'In Progress', handled_by = :staff_id WHERE request_id = :request_id
""")
CLOSE_SQL = text("""
    UPDATE customer_requests SET request_status = :outcome, resolved_at = now(), handled_by = coalesce(handled_by, :staff_id)
    WHERE request_id = :request_id
""")
# approved = being done (In Progress), rejected = closed now. Each value is sent once: asyncpg refuses one
# parameter used as two different types (varchar in a column, text in a CASE)
DECIDE_SQL = text("""
    UPDATE customer_requests SET decision = :decision, decided_by = :staff_id, decided_at = now(), handled_by = :staff_id,
           request_status = :new_status, resolved_at = CASE WHEN :closes THEN now() END
    WHERE request_id = :request_id
""")


async def ticket_state(db: AsyncConnection, request_id: str):
    state = (await db.execute(TICKET_STATE_SQL, {"request_id": request_id})).mappings().first()
    if state is None:
        raise refuse(404, "REQUEST_NOT_FOUND")
    if state["request_status"] in ("Resolved", "Closed"):
        raise refuse(409, "ALREADY_CLOSED")
    return state


async def ticket(db: AsyncConnection, request_id: str) -> Ticket:
    return Ticket(**(await db.execute(TICKET_SQL, {"request_id": request_id})).mappings().one())


@router.get("/staff/requests", response_model=list[Ticket])
async def queue(staff: CurrentAccount = Depends(get_current_staff), db: AsyncConnection = Depends(get_db)):
    return [Ticket(**row) for row in (await db.execute(QUEUE_SQL)).mappings().all()]


@router.post("/staff/requests/{request_id}/take", response_model=Ticket)
async def take(request_id: str, staff: CurrentAccount = Depends(get_current_staff),
               db: AsyncConnection = Depends(get_db)):
    """A member of staff takes the ticket: nobody else works on it twice."""
    state = await ticket_state(db, request_id)
    if state["request_status"] != "Open":
        raise refuse(409, "ALREADY_TAKEN")
    await db.execute(TAKE_SQL, {"request_id": state["request_id"], "staff_id": staff.account_id})
    await db.commit()
    return await ticket(db, state["request_id"])


@router.post("/staff/requests/{request_id}/close", response_model=Ticket)
async def close(request_id: str, body: CloseTicket, staff: CurrentAccount = Depends(get_current_staff),
                db: AsyncConnection = Depends(get_db)):
    state = await ticket_state(db, request_id)
    if state["request_type"] == "Discount Request" and state["decision"] is None:
        raise refuse(409, "ADMIN_DECIDES")          # only the admin answers a discount request
    await db.execute(CLOSE_SQL, {"request_id": state["request_id"], "outcome": body.outcome,
                                 "staff_id": staff.account_id})
    await db.commit()
    return await ticket(db, state["request_id"])


@router.post("/staff/requests/{request_id}/decision", response_model=Ticket)
async def decide(request_id: str, body: TicketDecision, staff: CurrentAccount = Depends(get_current_staff),
                 db: AsyncConnection = Depends(get_db)):
    """A Special Request (a late check-out, a celebration...): approved = being done, rejected = closed."""
    state = await ticket_state(db, request_id)
    if state["request_type"] != "Special Request":
        raise refuse(409, "NOT_A_SPECIAL_REQUEST")
    if state["decision"]:
        raise refuse(409, "ALREADY_DECIDED")
    approved = body.decision == "Approved"
    await db.execute(DECIDE_SQL, {"request_id": state["request_id"], "decision": body.decision,
                                  "staff_id": staff.account_id, "new_status": "In Progress" if approved else "Closed",
                                  "closes": not approved})
    await db.commit()
    return await ticket(db, state["request_id"])


# ---------- discount requests: the admin decides (queries.sql 11) ----------

DISCOUNT_REQUESTS_SQL = text("""
    SELECT r.request_id, r.customer_id, c.first_name || ' ' || c.last_name AS guest_name, r.booking_id,
           r.request_text, r.created_at
    FROM customer_requests r JOIN customers c USING (customer_id)
    WHERE r.request_type = 'Discount Request' AND r.decision IS NULL AND r.request_status IN ('Open', 'In Progress')
    ORDER BY r.created_at
""")
DISCOUNT_REQUEST_SQL = text("""
    SELECT r.request_id, r.customer_id, c.first_name, c.email
    FROM customer_requests r JOIN customers c USING (customer_id)
    WHERE r.request_id = upper(:request_id) AND r.request_type = 'Discount Request'
      AND r.decision IS NULL AND r.request_status IN ('Open', 'In Progress')
    FOR UPDATE OF r
""")
NEXT_CODE_ID_SQL = text("""
    SELECT 'DC' || lpad((coalesce(max(substr(code_id, 3)::int), 0) + 1)::text, 3, '0') FROM discount_codes
""")
# 11b: a personal one-time code for this guest, valid 30 days
NEW_CODE_SQL = text("""
    INSERT INTO discount_codes (code_id, discount_code, discount_type, discount_value, usage_count, max_usage,
                                start_date, end_date, status, customer_id)
    VALUES (:code_id, :discount_code, :discount_type, :discount_value, 0, 1,
            hotel_today(), hotel_today() + 30, 'Active', :customer_id)
    RETURNING end_date
""")
APPROVED_SQL = text("""
    UPDATE customer_requests SET decision = 'Approved', decided_by = :admin_id, decided_at = now(), issued_code_id = :code_id,
           request_status = 'Resolved', handled_by = :admin_id, resolved_at = now()
    WHERE request_id = :request_id
""")
REJECTED_SQL = text("""
    UPDATE customer_requests SET decision = 'Rejected', decided_by = :admin_id, decided_at = now(),
           request_status = 'Closed', handled_by = :admin_id, resolved_at = now()
    WHERE request_id = :request_id
""")


async def waiting_discount_request(db: AsyncConnection, request_id: str):
    found = (await db.execute(DISCOUNT_REQUEST_SQL, {"request_id": request_id})).mappings().first()
    if found is None:
        raise refuse(404, "DISCOUNT_REQUEST_NOT_FOUND")       # unknown, or already answered
    return found


def new_discount_code() -> str:
    return "NP" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))


@router.get("/admin/discount-requests", response_model=list[DiscountRequestOut])
async def discount_requests(admin: CurrentAccount = Depends(get_current_admin), db: AsyncConnection = Depends(get_db)):
    return [DiscountRequestOut(**row) for row in (await db.execute(DISCOUNT_REQUESTS_SQL)).mappings().all()]


@router.post("/admin/discount-requests/{request_id}/approve", response_model=DiscountDecision)
async def approve_discount(request_id: str, body: ApproveDiscount, background: BackgroundTasks,
                           admin: CurrentAccount = Depends(get_current_admin), db: AsyncConnection = Depends(get_db)):
    """Gives the guest a personal one-time code (30 days) and emails it to them."""
    found = await waiting_discount_request(db, request_id)
    for _ in range(3):   # two approvals at the same moment could pick the same next code id: try again
        code_id, code = (await db.execute(NEXT_CODE_ID_SQL)).scalar_one(), new_discount_code()
        try:
            async with db.begin_nested():
                valid_to = (await db.execute(NEW_CODE_SQL, {
                    "code_id": code_id, "discount_code": code, "discount_type": body.discount_type,
                    "discount_value": body.discount_value, "customer_id": found["customer_id"],
                })).scalar_one()
            break
        except IntegrityError:
            continue
    else:
        raise refuse(409, "TRY_AGAIN")
    await db.execute(APPROVED_SQL, {"request_id": found["request_id"], "admin_id": admin.account_id, "code_id": code_id})
    await db.commit()

    offer = f"{body.discount_value:g}% off" if body.discount_type == "PERCENTAGE" else f"{body.discount_value:,.2f} EGP off"
    background.add_task(send_discount_decision, found["email"], found["first_name"], code, offer, valid_to)
    return DiscountDecision(request_id=found["request_id"], decision="Approved", discount_code=code, valid_to=valid_to)


@router.post("/admin/discount-requests/{request_id}/reject", response_model=DiscountDecision)
async def reject_discount(request_id: str, background: BackgroundTasks,
                          admin: CurrentAccount = Depends(get_current_admin), db: AsyncConnection = Depends(get_db)):
    found = await waiting_discount_request(db, request_id)
    await db.execute(REJECTED_SQL, {"request_id": found["request_id"], "admin_id": admin.account_id})
    await db.commit()
    background.add_task(send_discount_decision, found["email"], found["first_name"], None, None, None)
    return DiscountDecision(request_id=found["request_id"], decision="Rejected")
