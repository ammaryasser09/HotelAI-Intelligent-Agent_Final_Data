from decimal import Decimal

from app.api.services.pricing import price_stay

RULES = {
    "long_stay_min_nights": 7,
    "deposit_nights": 1,
    "non_refundable_multiplier": Decimal("0.85"),
}


def test_suite_10_nights_gets_long_stay_discount():
    flexible, non_refundable = price_stay(Decimal("20000"), 10, Decimal("0.88"), **RULES)
    assert flexible.total == 200000
    assert flexible.discount.source == "Long Stay"
    assert flexible.discount.amount == 24000
    assert flexible.amount_due == 176000
    assert flexible.deposit_now == 20000
    assert flexible.pay_at_hotel == 156000
    assert non_refundable.total == 170000
    assert non_refundable.pay_now == 170000


def test_short_stay_has_no_discount():
    flexible, non_refundable = price_stay(Decimal("8000"), 3, Decimal("0.88"), **RULES)
    assert flexible.discount is None
    assert flexible.amount_due == 24000
    assert flexible.deposit_now == 8000
    assert flexible.pay_at_hotel == 16000
    assert non_refundable.total == 20400


def test_long_stay_switched_off_in_database():
    flexible, _ = price_stay(Decimal("20000"), 10, None, **RULES)
    assert flexible.discount is None
    assert flexible.amount_due == 200000


def code(discount_type, value):
    from app.api.schemas.discounts import DiscountCodeCheck

    return DiscountCodeCheck(code="TEST", usable=True, discount_type=discount_type, discount_value=float(value))


def test_bigger_discount_wins():
    # 10 nights: Long Stay 24,000 vs a 15% code 30,000 -> the code wins
    flexible, non_refundable = price_stay(Decimal("20000"), 10, Decimal("0.88"), **RULES, code=code("PERCENTAGE", "15"))
    assert flexible.discount.source == "Code"
    assert flexible.amount_due == 170000
    assert non_refundable.total == 170000   # Non-refundable never takes a code


def test_fixed_code_never_takes_the_whole_stay():
    # the database refuses a discount equal to the total, so at least 0.01 EGP is left
    flexible, _ = price_stay(Decimal("6000"), 1, Decimal("0.88"), **RULES, code=code("FIXED_AMOUNT", "9999"))
    assert flexible.discount.amount == 5999.99
    assert flexible.amount_due == 0.01
    assert flexible.deposit_now == 0.01
