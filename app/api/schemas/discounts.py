from datetime import date

from pydantic import BaseModel, Field


class DiscountCodeCheck(BaseModel):
    code: str
    usable: bool
    reason: str | None = None
    status: str | None = None
    discount_type: str | None = None
    discount_value: float | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    uses_left: int | None = None
    code_id: str | None = Field(default=None, exclude=True)  # used inside the API, never sent
