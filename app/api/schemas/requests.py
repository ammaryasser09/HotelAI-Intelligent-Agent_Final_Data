from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

# What a guest can ask for (customer_requests.request_type); staff-only types are not here
GuestRequestType = Literal[
    "Housekeeping", "Maintenance", "Room Service", "Extra Bed", "Late Checkout", "Early Check-in",
    "Airport Transfer", "Special Request", "Complaint", "Discount Request", "Payment Inquiry",
    "General Inquiry", "Staff Callback", "Emergency",
]
COMPLAINT_CATEGORIES = ("Room Issue", "Service Issue", "Facility Issue", "Billing Issue", "Booking Issue")
SPECIAL_REQUEST_CATEGORIES = ("Checkout Extension", "Service Request", "Celebration Arrangement",
                              "Dietary Requirement", "Transportation", "Accessibility Request", "Room Preference")


class NewRequest(BaseModel):
    request_type: GuestRequestType = Field(examples=["Housekeeping"])
    request_text: str = Field(min_length=3, max_length=1000, examples=["Two extra towels for room 401, please"])
    booking_id: str | None = Field(default=None, pattern=r"^[Bb]\d{6}$", examples=[None])
    category: str | None = Field(default=None, max_length=25, examples=[None])
    call_id: UUID | None = None        # set by the agent when the request comes from a call


class EmergencyRequest(BaseModel):
    request_text: str = Field(min_length=3, max_length=1000, examples=["Someone fainted in the lobby"])
    call_id: UUID | None = None


class RequestOut(BaseModel):
    request_id: str
    call_id: UUID | None                # the call (or website emergency) it came from
    request_type: str
    category: str | None
    priority: str
    request_status: str
    request_text: str
    booking_id: str | None
    decision: str | None
    discount_code: str | None = None   # an approved Discount Request: the personal code the guest got
    created_at: datetime
    resolved_at: datetime | None


class EmergencyOpened(BaseModel):
    request: RequestOut
    ambulance: str = "123"
    police: str = "122"
    fire: str = "180"
    reception: str


class LoyaltyStatus(BaseModel):
    member: bool
    tier: str | None = None
    points_balance: int | None = None
    points_worth_egp: float | None = None      # what the points take off a stay, in EGP
    total_stays: int | None = None
    late_checkout_until: str | None = None     # "14:00" for Gold; None = the standard 12:00
    benefits: str | None = None
