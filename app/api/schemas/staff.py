from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class DeskBooking(BaseModel):
    """A stay on the front-desk lists (arrivals, in house)."""
    booking_id: str
    first_name: str
    last_name: str
    room_type_name: str
    room_number: int
    check_in: date
    check_out: date
    nights: int
    adults: int
    children: int
    amount_due: float
    amount_paid: float
    balance_due: float            # what the guest still pays at the desk
    checked_in_at: datetime | None


class CheckOutRequest(BaseModel):
    payment_method: Literal["Cash", "Credit Card", "Debit Card", "Digital Wallet", "Bank Transfer"] = "Cash"


class DeskResult(BaseModel):
    booking_id: str
    booking_status: str
    room_number: int
    balance_paid: float = 0


class Ticket(BaseModel):
    request_id: str
    priority: str
    request_type: str
    category: str | None
    request_status: str
    request_text: str
    customer_id: str | None
    guest_name: str | None
    booking_id: str | None
    room_number: int | None
    call_id: UUID | None
    handled_by: str | None
    decision: str | None
    created_at: datetime


class CloseTicket(BaseModel):
    outcome: Literal["Resolved", "Closed"] = "Resolved"     # Closed = finished without being done


class TicketDecision(BaseModel):
    decision: Literal["Approved", "Rejected"]


class DiscountRequestOut(BaseModel):
    request_id: str
    customer_id: str
    guest_name: str
    booking_id: str | None
    request_text: str
    created_at: datetime


class ApproveDiscount(BaseModel):
    discount_type: Literal["PERCENTAGE", "FIXED_AMOUNT"] = "PERCENTAGE"
    discount_value: float = Field(gt=0, examples=[10])

    @model_validator(mode="after")
    def percentage_up_to_100(self):
        if self.discount_type == "PERCENTAGE" and self.discount_value > 100:
            raise ValueError("a percentage cannot be over 100")
        return self


class DiscountDecision(BaseModel):
    request_id: str
    decision: str
    discount_code: str | None = None
    valid_to: date | None = None
