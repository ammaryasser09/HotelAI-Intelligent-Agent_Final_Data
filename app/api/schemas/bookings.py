from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class BookingSummary(BaseModel):
    booking_id: str
    access: str
    booking_status: str
    rate_plan: str
    check_in: date
    check_out: date
    nights: int
    adults: int
    children: int
    room_type_name: str
    room_number: int
    view: str
    price_per_night: float
    total_amount: float
    discount_source: str | None
    discount_amount: float
    amount_due: float
    payment_status: str | None
    amount_paid: float | None
    refund_amount: float | None
    payment_due_at: datetime | None


class LinkBookingRequest(BaseModel):
    booking_ref: str = Field(pattern=r"^[Bb]\d{6}$", examples=["B000004"])
    last_name: str | None = Field(default=None, min_length=2, max_length=40, examples=["Almansoori"])
    phone_last4: str | None = Field(default=None, pattern=r"^\d{4}$", examples=["3877"])

    @model_validator(mode="after")
    def needs_proof(self):
        if not self.last_name and not self.phone_last4:
            raise ValueError("give last_name or phone_last4")
        return self
