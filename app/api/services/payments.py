import hashlib
import hmac
import logging
import uuid
from decimal import Decimal

import httpx
from fastapi import Request

from app.api.config import settings

logger = logging.getLogger("hotel_api")

# Paymob signs every transaction callback with these fields, in this order (HMAC-SHA512 with the HMAC secret)
HMAC_FIELDS = (
    "amount_cents", "created_at", "currency", "error_occured", "has_parent_transaction", "id",
    "integration_id", "is_3d_secure", "is_auth", "is_capture", "is_refunded", "is_standalone_payment",
    "is_voided", "order.id", "owner", "pending", "source_data.pan", "source_data.sub_type",
    "source_data.type", "success",
)


class PaymentProviderError(Exception):
    """Paymob could not be reached or refused the request."""


async def create_payment_link(request: Request, booking_id: str, amount: Decimal, guest) -> str:
    """The link the guest opens to pay. Every payment provider is called from here and only here."""
    if settings.payment_provider == "paymob":
        return await paymob_checkout_link(booking_id, amount, guest)
    return str(request.url_for("mock_payment_page", booking_id=booking_id))


async def paymob_checkout_link(booking_id: str, amount: Decimal, guest) -> str:
    cents = int((amount * 100).to_integral_value())
    base = settings.public_base_url.rstrip("/")
    body = {
        "amount": cents,
        "currency": "EGP",
        "payment_methods": [settings.paymob_integration_id],
        "items": [{"name": f"Nile Pearl Hotel booking {booking_id}", "amount": cents, "quantity": 1}],
        "billing_data": {
            "first_name": guest["first_name"], "last_name": guest["last_name"],
            "email": guest["email"], "phone_number": guest["phone"],
            "apartment": "NA", "floor": "NA", "building": "NA", "street": "NA",
            "city": "Cairo", "state": "Cairo", "country": "EGY",
        },
        # comes back in the callback as merchant_order_id; a suffix keeps it unique if a link is made again
        "special_reference": f"{booking_id}-{uuid.uuid4().hex[:8]}",
        "notification_url": f"{base}/payments/paymob/webhook",
        "redirection_url": f"{base}/payments/paymob/return",
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                settings.paymob_intention_url,
                json=body,
                headers={"Authorization": f"Token {settings.paymob_secret_key}"},
            )
    except httpx.HTTPError as error:
        logger.error("Paymob could not be reached: %s", error)
        raise PaymentProviderError("unreachable") from error
    if response.status_code >= 300:
        logger.error("Paymob refused the payment intention: %s %s", response.status_code, response.text[:500])
        raise PaymentProviderError("refused")

    client_secret = response.json()["client_secret"]
    return f"{settings.paymob_checkout_url}?publicKey={settings.paymob_public_key}&clientSecret={client_secret}"


def _field(obj: dict, path: str) -> str:
    value = obj
    for part in path.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else str(value)


def paymob_signature(obj: dict) -> str:
    message = "".join(_field(obj, path) for path in HMAC_FIELDS)
    return hmac.new(settings.paymob_hmac_secret.encode(), message.encode(), hashlib.sha512).hexdigest()


def paymob_signature_is_valid(obj: dict, received: str) -> bool:
    # compare_digest takes the same time for any mismatch, so the signature cannot be guessed piece by piece
    return bool(received) and hmac.compare_digest(paymob_signature(obj), received)


def booking_of(obj: dict) -> str:
    """special_reference "B020001-1a2b3c4d" comes back as order.merchant_order_id."""
    reference = (obj.get("order") or {}).get("merchant_order_id") or ""
    return reference.split("-")[0]


# payments.transaction_reference only takes a UUID, so Paymob's transaction number is kept inside one:
# 987654 -> 00000000-0000-0000-0000-0000000f1206. The demo data's random UUIDs are never that small.
def paymob_reference(transaction_id) -> str:
    return str(uuid.UUID(int=int(transaction_id)))


def paymob_transaction_id(reference) -> int | None:
    number = uuid.UUID(str(reference)).int
    return number if number < 2**63 else None


async def refund_payment(booking_id: str, amount: Decimal, reference) -> None:
    """Sends money back to the guest's card. Paid through Paymob: Paymob refunds it.
    Paid with the fake Paymob, or a demo booking: there is no real card payment, so it is only recorded."""
    if amount <= 0:
        return
    transaction_id = paymob_transaction_id(reference)
    if settings.payment_provider != "paymob" or transaction_id is None:
        logger.info("Refund of %s EGP for %s recorded (no real card payment to send it back to)", amount, booking_id)
        return

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            # the refund API still uses Paymob's older login: API key -> short-lived auth token
            auth = await client.post(settings.paymob_auth_url, json={"api_key": settings.paymob_api_key})
            auth.raise_for_status()
            response = await client.post(settings.paymob_refund_url, json={
                "auth_token": auth.json()["token"],
                "transaction_id": transaction_id,
                "amount_cents": int((amount * 100).to_integral_value()),
            })
            response.raise_for_status()
    except (httpx.HTTPError, KeyError, ValueError) as error:
        logger.error("Paymob refund for %s failed: %s", booking_id, error)
        raise PaymentProviderError("refund failed") from error
    if str(response.json().get("obj", {}).get("success")).lower() != "true":
        logger.error("Paymob refused the refund for %s: %s", booking_id, response.text[:500])
        raise PaymentProviderError("refund refused")
    logger.info("Paymob refunded %s EGP for %s", amount, booking_id)
