from decimal import ROUND_HALF_UP, Decimal

from app.api.schemas.availability import Discount, FlexiblePrice, NonRefundablePrice

CENT = Decimal("0.01")


def money(value: Decimal) -> float:
    return float(value.quantize(CENT, rounding=ROUND_HALF_UP))


def price_stay(
    rate_per_night: Decimal,
    nights: int,
    long_stay_multiplier: Decimal | None,
    long_stay_min_nights: int,
    deposit_nights: int,
    non_refundable_multiplier: Decimal,
) -> tuple[FlexiblePrice, NonRefundablePrice]:
    total = rate_per_night * nights

    discount = None
    discount_amount = Decimal(0)
    if long_stay_multiplier is not None and nights >= long_stay_min_nights:
        discount_amount = total * (1 - long_stay_multiplier)
        discount = Discount(source="Long Stay", amount=money(discount_amount))

    amount_due = total - discount_amount
    deposit = rate_per_night * min(nights, deposit_nights)

    flexible = FlexiblePrice(
        rate_per_night=money(rate_per_night),
        total=money(total),
        discount=discount,
        amount_due=money(amount_due),
        deposit_now=money(deposit),
        pay_at_hotel=money(amount_due - deposit),
    )

    non_refundable_total = total * non_refundable_multiplier
    non_refundable = NonRefundablePrice(
        total=money(non_refundable_total),
        pay_now=money(non_refundable_total),
    )
    return flexible, non_refundable