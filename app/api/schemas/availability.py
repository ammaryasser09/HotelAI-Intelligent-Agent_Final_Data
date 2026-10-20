from datetime import date

from pydantic import BaseModel, Field, model_validator


class AvailabilityQuery(BaseModel):
    room_type: str = Field(min_length=2, max_length=30, examples=["Suite"])
    check_in: date = Field(examples=["2026-10-03"])
    check_out: date = Field(examples=["2026-10-06"])
    guests: int = Field(default=1, ge=1, le=10)
    discount_code: str | None = Field(default=None, min_length=3, max_length=20, examples=["PEARL100"])

    @model_validator(mode="after")
    def check_out_after_check_in(self):
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        return self

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days


class RoomImages(BaseModel):
    nile: str | None
    city: str | None


class Discount(BaseModel):
    source: str
    code: str | None = None
    amount: float


class FlexiblePrice(BaseModel):
    rate_per_night: float
    total: float
    discount: Discount | None
    amount_due: float
    deposit_now: float
    pay_at_hotel: float


class NonRefundablePrice(BaseModel):
    total: float
    pay_now: float


class Alternative(BaseModel):
    room_type: str
    capacity: int
    rate_per_night: float
    rooms_free: int


class AvailabilityResult(BaseModel):
    room_type: str
    check_in: date
    check_out: date
    nights: int
    guests: int
    rooms_free: int
    nile_view_free: int
    free_room_numbers: list[int]
    images: RoomImages
    flexible: FlexiblePrice
    non_refundable: NonRefundablePrice
    alternatives: list[Alternative]
    discount_code_not_used: str | None = None
