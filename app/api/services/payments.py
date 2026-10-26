from decimal import Decimal

from fastapi import Request

from app.api.config import settings


async def create_payment_link(request: Request, booking_id: str, amount: Decimal) -> str:
    """The link the guest opens to pay. Every payment provider is called from here and only here."""
    if settings.payment_provider == "paymob":
        # Paymob test mode comes next; until then the fake page keeps the whole flow working
        raise NotImplementedError("PAYMENT_PROVIDER=paymob is not wired yet: use mock")
    return str(request.url_for("mock_payment_page", booking_id=booking_id))
