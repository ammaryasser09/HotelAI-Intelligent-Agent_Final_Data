from decimal import ROUND_HALF_UP, Decimal

from app.api.schemas.availability import Discount, FlexiblePrice, NonRefundablePrice
from app.api.schemas.discounts import DiscountCodeCheck

CENT = Decimal("0.01")


def money(value: Decimal) -> float:
    return float(value.quantize(CENT, rounding=ROUND_HALF_UP))


def code_amount(code: DiscountCodeCheck, total: Decimal) -> Decimal:
    value = Decimal(str(code.discount_value))
    if code.discount_type == "PERCENTAGE":
        return total * value / 100
    return min(value, total - CENT)  # the database needs the discount to stay below the total


def price_stay(
    rate_per_night: Decimal,
    nights: int,
    long_stay_multiplier: Decimal | None,
    long_stay_min_nights: int,
    deposit_nights: int,
    non_refundable_multiplier: Decimal,
    code: DiscountCodeCheck | None = None,
) -> tuple[FlexiblePrice, NonRefundablePrice]:
    total = rate_per_night * nights

    # One discount at most, Flexible rate only: Long Stay (7+ nights) or a usable code, the bigger
    options: list[tuple[Decimal, Discount]] = []
    if long_stay_multiplier is not None and nights >= long_stay_min_nights:
        amount = total * (1 - long_stay_multiplier)
        options.append((amount, Discount(source="Long Stay", amount=money(amount))))
    if code is not None and code.usable:
        amount = code_amount(code, total)
        options.append((amount, Discount(source="Code", code=code.code, amount=money(amount))))

    discount_amount, discount = max(options, key=lambda option: option[0]) if options else (Decimal(0), None)

    amount_due = total - discount_amount
    deposit = min(rate_per_night * min(nights, deposit_nights), amount_due)

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
