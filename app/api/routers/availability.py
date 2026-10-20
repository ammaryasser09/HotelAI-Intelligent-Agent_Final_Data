from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.config import settings
from app.api.db import get_db
from app.api.schemas.availability import (
    Alternative,
    AvailabilityQuery,
    AvailabilityResult,
    RoomImages,
)
from app.api.services.pricing import price_stay

router = APIRouter(tags=["Availability"])

# queries.sql 1a
ROOM_TYPE_SQL = text("""
    SELECT room_type_id, room_type_name, capacity, base_price, image_nile, image_city
    FROM room_types
    WHERE room_type_id = upper(:room_type) OR lower(room_type_name) = lower(:room_type)
""")

# "today" and the pricing rules, read from the database in one round trip
HOTEL_RULES_SQL = text("""
    SELECT hotel_today() AS today,
           (SELECT value::int FROM app_settings WHERE key = 'deposit_nights') AS deposit_nights,
           (SELECT rate_multiplier FROM pricing_tiers
             WHERE tier_name = 'Extended Stay' AND status = 'Active') AS long_stay_multiplier
""")

# queries.sql 1b
FREE_ROOMS_SQL = text("""
    SELECT room_number, floor, view
    FROM free_rooms(:room_type, :check_in, :check_out)
""")

# queries.sql 1c
ALTERNATIVES_SQL = text("""
    SELECT t.room_type_name, t.capacity, t.base_price, count(f.room_number) AS rooms_free
    FROM room_types t
    CROSS JOIN LATERAL free_rooms(t.room_type_id, :check_in, :check_out) f
    WHERE t.capacity >= :guests
    GROUP BY t.room_type_id, t.room_type_name, t.capacity, t.base_price
    ORDER BY t.base_price
""")


@router.get("/availability", response_model=AvailabilityResult)
async def check_availability(
    query: Annotated[AvailabilityQuery, Query()],
    db: AsyncConnection = Depends(get_db),
):
    room_type = (await db.execute(ROOM_TYPE_SQL, {"room_type": query.room_type})).mappings().first()
    if room_type is None:
        names = (await db.execute(
            text("SELECT room_type_name FROM room_types ORDER BY base_price")
        )).scalars().all()
        raise HTTPException(
            status_code=404,
            detail={"reason": "UNKNOWN_ROOM_TYPE", "room_types": names},
        )

    rules = (await db.execute(HOTEL_RULES_SQL)).mappings().one()
    if query.check_in < rules["today"]:
        raise HTTPException(
            status_code=400,
            detail={"reason": "CHECK_IN_IN_THE_PAST", "today": str(rules["today"])},
        )

    if query.guests > room_type["capacity"]:
        fits = (await db.execute(
            text("SELECT room_type_name FROM room_types WHERE capacity >= :guests ORDER BY base_price"),
            {"guests": query.guests},
        )).scalars().all()
        raise HTTPException(
            status_code=400,
            detail={
                "reason": "CAPACITY_EXCEEDED",
                "capacity": room_type["capacity"],
                "room_types_that_fit": fits,
            },
        )

    stay = {"check_in": query.check_in, "check_out": query.check_out}

    free = (await db.execute(
        FREE_ROOMS_SQL, {"room_type": room_type["room_type_id"], **stay}
    )).mappings().all()

    alternatives = []
    if not free:
        rows = (await db.execute(
            ALTERNATIVES_SQL, {"guests": query.guests, **stay}
        )).mappings().all()
        alternatives = [
            Alternative(
                room_type=row["room_type_name"],
                capacity=row["capacity"],
                rate_per_night=float(row["base_price"]),
                rooms_free=row["rooms_free"],
            )
            for row in rows
        ]

    flexible, non_refundable = price_stay(
        rate_per_night=room_type["base_price"],
        nights=query.nights,
        long_stay_multiplier=rules["long_stay_multiplier"],
        long_stay_min_nights=settings.long_stay_min_nights,
        deposit_nights=rules["deposit_nights"] or 1,
        non_refundable_multiplier=settings.non_refundable_multiplier,
    )

    return AvailabilityResult(
        room_type=room_type["room_type_name"],
        check_in=query.check_in,
        check_out=query.check_out,
        nights=query.nights,
        guests=query.guests,
        rooms_free=len(free),
        nile_view_free=sum(1 for room in free if room["view"] == "Nile"),
        free_room_numbers=[room["room_number"] for room in free],
        images=RoomImages(
            nile=room_type["image_nile"] or None,
            city=room_type["image_city"] or None,
        ),
        flexible=flexible,
        non_refundable=non_refundable,
        alternatives=alternatives,
    )
