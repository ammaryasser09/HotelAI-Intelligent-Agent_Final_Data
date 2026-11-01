import logging
import re
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from starlette.concurrency import run_in_threadpool

from app.api.config import settings
from app.api.db import engine

logger = logging.getLogger("hotel_api")

# EMAIL_PROVIDER=log: every email is written here as a text file instead of being sent (logs/ is not committed)
EMAIL_DIR = Path(__file__).resolve().parents[3] / "logs" / "emails"

DETAILS_SQL = text("""
    SELECT d.booking_id, d.booking_status, d.first_name, d.last_name, d.email, d.room_type_name, d.room_number,
           d.view, d.check_in, d.check_out, d.nights, d.adults, d.children, d.rate_plan, d.amount_due,
           d.amount_paid, d.refund_amount, d.payment_status,
           (SELECT value FROM app_settings WHERE key = 'reservations_phone') AS reservations_phone,
           (SELECT value FROM app_settings WHERE key = 'reception_phone') AS reception_phone
    FROM v_booking_details d
    WHERE d.booking_id = :booking_id
""")

SUBJECTS = {
    "confirmed": "Your booking {id} is confirmed",
    "changed": "Your booking {id} has been changed",
    "cancelled": "Your booking {id} has been cancelled",
    "expired": "Your booking {id} was cancelled: payment not received",
}
OPENINGS = {
    "confirmed": "Thank you, your payment was received and your booking is confirmed.",
    "changed": "Your booking has been changed. Here are the new details.",
    "cancelled": "Your booking has been cancelled as you asked.",
    "expired": ("We did not receive the payment in time, so the booking was cancelled and the room released. "
                "You are welcome to book again."),
}


def egp(value) -> str:
    return f"{value:,.2f} EGP"


def compose(kind: str, b) -> tuple[str, str]:
    guests = f"{b['adults']} adult{'s' if b['adults'] > 1 else ''}"
    if b["children"]:
        guests += f", {b['children']} child{'ren' if b['children'] > 1 else ''}"
    held = b["amount_paid"] - b["refund_amount"]
    lines = [
        f"Dear {b['first_name']} {b['last_name']},",
        "",
        OPENINGS[kind],
        "",
        f"Booking:    {b['booking_id']}",
        f"Room:       {b['room_type_name']}, room {b['room_number']} ({b['view']} view)",
        f"Check-in:   {b['check_in']:%a %d %b %Y}, from 3:00 PM",
        f"Check-out:  {b['check_out']:%a %d %b %Y}, by 12:00 PM",
        f"Nights:     {b['nights']}   Guests: {guests}",
        f"Rate:       {b['rate_plan']}",
    ]
    if b["booking_status"] in ("Pending", "Confirmed"):
        lines += [f"Stay total: {egp(b['amount_due'])}", f"Paid:       {egp(held)}",
                  f"To pay at the hotel: {egp(b['amount_due'] - held)}"]
    if b["refund_amount"] > 0:
        lines.append(f"Refunded to your card: {egp(b['refund_amount'])} (it can take a few days to appear)")
    lines += [
        "",
        f"Questions? Reservations {b['reservations_phone']}, reception (24/7) {b['reception_phone']}.",
        "",
        "Nile Pearl Hotel",
        "14 Corniche El Nil, Garden City, Cairo",
    ]
    return SUBJECTS[kind].format(id=b["booking_id"]), "\n".join(lines)


def _send_smtp(message: EmailMessage) -> None:
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)


async def deliver(to: str, subject: str, body: str) -> None:
    if settings.email_provider == "smtp":
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = settings.email_from, to, subject
        message.set_content(body)
        await run_in_threadpool(_send_smtp, message)   # smtplib waits on the network: keep it off the event loop
        return
    EMAIL_DIR.mkdir(parents=True, exist_ok=True)
    booking = re.search(r"B\d{6}", subject)
    name = f"{datetime.now():%Y%m%d-%H%M%S-%f}-{booking.group() if booking else 'code'}.txt"
    (EMAIL_DIR / name).write_text(f"To: {to}\nSubject: {subject}\n\n{body}\n", encoding="utf-8")


async def notify(booking_id: str, kind: str, db: AsyncConnection | None = None) -> None:
    """Emails the guest about their booking. Runs after the change is saved, and a failure here only gets
    logged: an email that could not be sent must never undo a payment, a cancellation or a change."""
    try:
        if db is None:
            async with engine.connect() as own_db:
                booking = (await own_db.execute(DETAILS_SQL, {"booking_id": booking_id})).mappings().first()
        else:
            booking = (await db.execute(DETAILS_SQL, {"booking_id": booking_id})).mappings().first()
        if booking is None:
            return
        subject, body = compose(kind, booking)
        await deliver(booking["email"], subject, body)
        logger.info("Email '%s' sent for %s", kind, booking_id)
    except Exception:
        logger.exception("Email '%s' for %s could not be sent", kind, booking_id)


CODE_EMAILS = {
    "verify_email": ("Your Nile Pearl Hotel verification code",
                     "Welcome to Nile Pearl Hotel! To confirm your email, enter this code:"),
    "reset_password": ("Reset your Nile Pearl Hotel password",
                       "Someone asked to reset your password. If it was you, enter this code:"),
}


async def send_code(to: str, first_name: str, code: str, purpose: str, minutes: int) -> None:
    """Emails a 6-digit code. Like notify(), a failure is only logged."""
    subject, opening = CODE_EMAILS[purpose]
    body = "\n".join([
        f"Dear {first_name},", "", opening, "", f"    {code}", "",
        f"It works for {minutes} minutes. Never share it: hotel staff will never ask you for it.",
        "If you did not ask for this, you can ignore this email.", "", "Nile Pearl Hotel",
    ])
    try:
        await deliver(to, subject, body)
        logger.info("Email code '%s' sent", purpose)
    except Exception:
        logger.exception("Email code '%s' could not be sent", purpose)


async def send_discount_decision(to: str, first_name: str, code: str | None, offer: str | None, valid_to) -> None:
    """The admin's answer to a Discount Request: the personal code, or a polite no."""
    if code:
        subject = "Your Nile Pearl Hotel discount code"
        middle = [f"Good news: your discount request was approved. Your personal code gives {offer}:", "",
                  f"    {code}", "", f"Use it on your next booking by {valid_to:%d %b %Y}. It works once, for you only."]
    else:
        subject = "About your discount request"
        middle = ["Thank you for your request. We are sorry, we cannot offer a discount this time.",
                  "Our Long Stay rate (7 nights or more) and our offers are always available on our website."]
    body = "\n".join([f"Dear {first_name},", "", *middle, "", "Nile Pearl Hotel"])
    try:
        await deliver(to, subject, body)
        logger.info("Discount decision email sent")
    except Exception:
        logger.exception("Discount decision email could not be sent")
