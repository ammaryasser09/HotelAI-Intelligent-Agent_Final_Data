from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.api.schemas.auth import EMAIL_PATTERN, Password


class StatsQuery(BaseModel):
    date_from: date | None = Field(default=None, examples=["2026-08-21"])   # default: the 30 days up to today
    date_to: date | None = Field(default=None, examples=["2026-09-19"])


class DayStats(BaseModel):
    day: date
    rooms_sold: int
    occupancy: float            # 0.82 = 82% of the rooms were taken that night
    revenue: float


class GroupStats(BaseModel):
    name: str
    room_nights: int
    revenue: float


class Stats(BaseModel):
    date_from: date
    date_to: date
    rooms: int                  # rooms that can be sold (not in maintenance)
    room_nights_sold: int
    occupancy: float
    revenue: float              # room revenue of the nights in the period, after discounts
    adr: float                  # average daily rate: revenue per room sold
    revpar: float               # revenue per available room
    bookings_made: int          # bookings created in the period
    cancellation_rate: float    # of the stays arriving in the period
    by_channel: list[GroupStats]
    by_room_type: list[GroupStats]
    daily: list[DayStats]
    open_tickets: dict[str, int]               # by priority
    avg_resolution_hours: float | None         # tickets resolved in the period


class StaffAccount(BaseModel):
    account_id: int
    role: str
    full_name: str
    email: str
    is_active: bool
    last_login_at: datetime | None


class NewStaff(BaseModel):
    full_name: Annotated[str, Field(min_length=3, max_length=80, examples=["Salma Adel"])]
    email: str = Field(max_length=120, pattern=EMAIL_PATTERN, examples=["salma.adel@nilepearlhotel.example"])
    password: Password


class NewPassword(BaseModel):
    new_password: Password

