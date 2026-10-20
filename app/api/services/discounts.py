from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.schemas.discounts import DiscountCodeCheck

# queries.sql 6
DISCOUNT_CODE_SQL = text("""
    SELECT discount_code, discount_type, discount_value, status, start_date, end_date, customer_id,
           CASE WHEN max_usage IS NULL THEN NULL ELSE max_usage - usage_count END AS uses_left,
           hotel_today() AS today
    FROM discount_codes
    WHERE discount_code = upper(:code)
""")


async def check_code(db: AsyncConnection, code: str, customer_id: str | None = None) -> DiscountCodeCheck | None:
    """None when the code does not exist. A personal code works only for its own guest."""
    row = (await db.execute(DISCOUNT_CODE_SQL, {"code": code.strip()})).mappings().first()
    if row is None:
        return None

    if row["customer_id"] is not None and row["customer_id"] != customer_id:
        reason = "PERSONAL_CODE_LOGIN_REQUIRED" if customer_id is None else "PERSONAL_CODE_OF_ANOTHER_GUEST"
        return DiscountCodeCheck(code=row["discount_code"], usable=False, reason=reason)

    in_dates = row["start_date"] <= row["today"] <= row["end_date"]
    has_uses = row["uses_left"] is None or row["uses_left"] > 0
    usable = row["status"] == "Active" and in_dates and has_uses

    return DiscountCodeCheck(
        code=row["discount_code"],
        usable=usable,
        reason=None if usable else "CODE_NOT_ACTIVE",
        status=row["status"],
        discount_type=row["discount_type"],
        discount_value=row["discount_value"],
        valid_from=row["start_date"],
        valid_to=row["end_date"],
        uses_left=row["uses_left"],
    )
