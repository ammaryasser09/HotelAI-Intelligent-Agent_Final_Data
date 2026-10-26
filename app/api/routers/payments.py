from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.config import settings
from app.api.db import get_db
from app.api.schemas.bookings import PaymentResult
from app.api.services.bookings import amount_to_pay_now, confirm_payment, payment_state
from app.api.services.pricing import money

router = APIRouter(tags=["Payments (mock)"])

PAGE = """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Mock payment</title>
<style>body{{font-family:system-ui,sans-serif;max-width:420px;margin:48px auto;padding:0 16px}}
.box{{border:1px solid #ccc;border-radius:8px;padding:20px}}button{{font-size:18px;padding:10px 24px}}</style></head>
<body><div class="box"><h2>Nile Pearl Hotel</h2>
<p>صفحة دفع تجريبية (Paymob وهمي). مفيش فلوس حقيقية.</p>
<p>الحجز: <b>{booking_id}</b><br>المبلغ: <b>{amount:,.2f} EGP</b></p>
<button onclick="pay()">ادفع</button><p id="out"></p></div>
<script>async function pay(){{const r=await fetch(location.pathname+'/pay',{{method:'POST'}});
const j=await r.json();document.getElementById('out').textContent=r.ok?'تم الدفع، والحجز بقى '+j.booking_status:'مرفوض: '+JSON.stringify(j.detail);}}</script>
</body></html>"""


def mock_only():
    if settings.payment_provider != "mock":
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


@router.get("/payments/mock/{booking_id}", response_class=HTMLResponse, name="mock_payment_page",
            dependencies=[Depends(mock_only)])
async def mock_payment_page(booking_id: str, db: AsyncConnection = Depends(get_db)):
    state = await payable(db, booking_id)
    return PAGE.format(booking_id=state["booking_id"], amount=amount_to_pay_now(state))


@router.post("/payments/mock/{booking_id}/pay", response_model=PaymentResult, dependencies=[Depends(mock_only)])
async def mock_pay(booking_id: str, db: AsyncConnection = Depends(get_db)):
    """Stands in for Paymob telling us the guest paid (the webhook)."""
    state = await payable(db, booking_id)
    amount = amount_to_pay_now(state)
    await confirm_payment(db, state["booking_id"], amount)
    return PaymentResult(booking_id=state["booking_id"], booking_status="Confirmed",
                         payment_status="Paid", amount_paid=money(amount))
