from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.api.schemas.availability import Discount


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


class CreateBookingRequest(BaseModel):
    room_type: str = Field(min_length=2, max_length=30, examples=["Double"])
    check_in: date = Field(examples=["2027-11-10"])
    check_out: date = Field(examples=["2027-11-13"])
    adults: int = Field(default=1, ge=1, le=10)
    children: int = Field(default=0, ge=0, le=10)
    rate_plan: Literal["Flexible", "Non-refundable"] = "Flexible"
    discount_code: str | None = Field(default=None, min_length=3, max_length=20, examples=[None])
    payment_method: Literal["Credit Card", "Debit Card", "Digital Wallet"] = "Credit Card"
    channel: Literal["Website", "Voice Agent", "Mobile App"] = "Website"

    @model_validator(mode="after")
    def check_out_after_check_in(self):
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        return self

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days

    @property
    def guests(self) -> int:
        return self.adults + self.children


class BookingCreated(BaseModel):
    booking_id: str
    booking_status: str
    room_type: str
    room_number: int
    view: str
    check_in: date
    check_out: date
    nights: int
    adults: int
    children: int
    rate_plan: str
    price_per_night: float
    total_amount: float
    discount: Discount | None
    amount_due: float
    pay_now: float
    pay_at_hotel: float
    payment_due_at: datetime
    payment_url: str
    discount_code_not_used: str | None = None


class PaymentResult(BaseModel):
    booking_id: str
    booking_status: str
    payment_status: str
    amount_paid: float


class CancellationQuote(BaseModel):
    """What cancelling now would cost. Nothing is changed by asking."""
    booking_id: str
    booking_status: str
    rate_plan: str
    check_in: date
    free_cancellation_until: datetime | None   # hotel time; None for Non-refundable (never free)
    is_free: bool
    amount_paid: float                          # what the hotel holds now
    charge: float                               # what the hotel keeps if cancelled now
    refund: float                               # what goes back to the guest's card


class CancellationResult(BaseModel):
    booking_id: str
    booking_status: str
    payment_status: str
    charge: float
    refund: float
