import logging
from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.config import settings
from app.api.db import get_db
from app.api.schemas.bookings import PaymentResult
from app.api.services.bookings import amount_to_pay_now, confirm_payment, payment_state
from app.api.services.email import notify
from app.api.services.payments import booking_of, paymob_reference, paymob_signature_is_valid
from app.api.services.pricing import money

logger = logging.getLogger("hotel_api")
router = APIRouter(tags=["Payments"])

PAGE_START = """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Nile Pearl Hotel</title>
<style>body{font-family:system-ui,sans-serif;max-width:420px;margin:48px auto;padding:0 16px}
.box{border:1px solid #ccc;border-radius:8px;padding:20px}button{font-size:18px;padding:10px 24px}</style></head>
<body><div class="box"><h2>Nile Pearl Hotel</h2>"""
PAGE_END = "</div></body></html>"

MOCK_BODY = """<p>صفحة دفع تجريبية (Paymob وهمي). مفيش فلوس حقيقية.</p>
<p>الحجز: <b>{booking_id}</b><br>المبلغ: <b>{amount:,.2f} EGP</b></p>
<button onclick="pay()">ادفع</button><p id="out"></p>
<script>async function pay(){{const r=await fetch(location.pathname+'/pay',{{method:'POST'}});
const j=await r.json();document.getElementById('out').textContent=r.ok?'تم الدفع، والحجز بقى '+j.booking_status:'مرفوض: '+JSON.stringify(j.detail);}}</script>"""


def mock_only():
    if settings.payment_provider != "mock":
        raise HTTPException(status_code=404, detail={"reason": "NOT_FOUND"})


def paymob_only():
    if settings.payment_provider != "paymob":
        raise HTTPException(status_code=404, detail={"reason": "NOT_FOUND"})


async def payable(db: AsyncConnection, booking_id: str):
    state = await payment_state(db, booking_id)
    if state is None:
        raise HTTPException(status_code=404, detail={"reason": "BOOKING_NOT_FOUND"})
    if state["booking_status"] != "Pending" or state["payment_status"] != "Pending":
        raise HTTPException(status_code=409, detail={"reason": "NOT_WAITING_FOR_PAYMENT",
                                                     "booking_status": state["booking_status"]})
    if state["overdue"]:
        raise HTTPException(status_code=409, detail={"reason": "PAYMENT_EXPIRED"})
    return state


# ---------- the fake Paymob (PAYMENT_PROVIDER=mock) ----------

@router.get("/payments/mock/{booking_id}", response_class=HTMLResponse, name="mock_payment_page",
            dependencies=[Depends(mock_only)])
async def mock_payment_page(booking_id: str, db: AsyncConnection = Depends(get_db)):
    state = await payable(db, booking_id)
    body = MOCK_BODY.format(booking_id=state["booking_id"], amount=amount_to_pay_now(state))
    return PAGE_START + body + PAGE_END


@router.post("/payments/mock/{booking_id}/pay", response_model=PaymentResult, dependencies=[Depends(mock_only)])
async def mock_pay(booking_id: str, background: BackgroundTasks, db: AsyncConnection = Depends(get_db)):
    """Stands in for Paymob telling us the guest paid (the webhook)."""
    state = await payable(db, booking_id)
    amount = amount_to_pay_now(state)
    await confirm_payment(db, state["booking_id"], amount)
    background.add_task(notify, state["booking_id"], "confirmed")   # sent after the answer, never delays it
    return PaymentResult(booking_id=state["booking_id"], booking_status="Confirmed",
                         payment_status="Paid", amount_paid=money(amount))


# ---------- the real Paymob (PAYMENT_PROVIDER=paymob) ----------

@router.post("/payments/paymob/webhook", dependencies=[Depends(paymob_only)])
async def paymob_webhook(request: Request, background: BackgroundTasks, hmac: str = Query(default=""),
                         db: AsyncConnection = Depends(get_db)):
    """Paymob calls this after every payment attempt (the notification_url)."""
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail={"reason": "NOT_JSON"})
    obj = payload.get("obj") if isinstance(payload, dict) else None
    if not isinstance(obj, dict) or payload.get("type") != "TRANSACTION" or not paymob_signature_is_valid(obj, hmac):
        logger.warning("Paymob callback with a wrong signature was refused")
        raise HTTPException(status_code=403, detail={"reason": "INVALID_SIGNATURE"})

    booking_ref = booking_of(obj)
    if obj.get("has_parent_transaction") or obj.get("is_refund") or obj.get("is_void"):
        # the callback of a refund we asked for (it points to the original payment): nothing more to do
        logger.info("Paymob: refund for %s went through", booking_ref)
        return {"received": True}
    if obj.get("success") is not True or obj.get("pending") is True:
        logger.info("Paymob: payment for %s did not go through", booking_ref)
        return {"received": True}

    state = await payment_state(db, booking_ref)
    if state is None:
        logger.warning("Paymob: paid for unknown booking %r", booking_ref)
    elif state["booking_status"] == "Pending" and state["payment_status"] == "Pending":
        paid = Decimal(obj["amount_cents"]) / 100
        if paid < amount_to_pay_now(state):
            logger.warning("Paymob: %s paid %s, less than asked, not confirmed", booking_ref, paid)
        else:
            await confirm_payment(db, booking_ref, paid, paymob_reference(obj["id"]))
            background.add_task(notify, booking_ref, "confirmed")
            logger.info("Paymob: booking %s confirmed", booking_ref)
    else:
        # e.g. the booking was cancelled for non-payment a moment before: the money must go back
        logger.warning("Paymob: %s paid but the booking is %s, refund needed", booking_ref, state["booking_status"])
    return {"received": True}


@router.get("/payments/paymob/return", response_class=HTMLResponse, dependencies=[Depends(paymob_only)])
async def paymob_return(merchant_order_id: str = "", success: str = "", db: AsyncConnection = Depends(get_db)):
    """Where Paymob sends the guest's browser after paying (the redirection_url). Changes nothing."""
    state = await payment_state(db, merchant_order_id.split("-")[0]) if merchant_order_id else None
    if success != "true":
        message = "<p>الدفع ماتمّش. تقدر تجرّب تاني من نفس اللينك.</p>"
    elif state and state["booking_status"] == "Confirmed":
        message = f"<p>تم الدفع ✓ وحجزك <b>{state['booking_id']}</b> اتأكد.</p>"
    else:
        message = "<p>تم الدفع ✓ وبنأكد الحجز دلوقتي، هيوصلك التأكيد خلال لحظات.</p>"
    return PAGE_START + message + PAGE_END
