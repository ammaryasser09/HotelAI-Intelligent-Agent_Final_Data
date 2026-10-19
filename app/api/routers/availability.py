from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.db import get_db
from app.api.schemas.availability import AvailabilityQuery, AvailabilityResult, RoomImages

router = APIRouter(tags=["Availability"])

ROOM_TYPE_SQL = text("""
    SELECT room_type_id, room_type_name, capacity, base_price, image_nile, image_city
    FROM room_types
    WHERE room_type_id = upper(:room_type) OR lower(room_type_name) = lower(:room_type)
""")

FREE_ROOMS_SQL = text("""
    SELECT room_number, floor, view
    FROM free_rooms(:room_type, :check_in, :check_out)
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

    today = (await db.execute(text("SELECT hotel_today()"))).scalar_one()
    if query.check_in < today:
        raise HTTPException(
            status_code=400,
            detail={"reason": "CHECK_IN_IN_THE_PAST", "today": str(today)},
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

    free = (await db.execute(
        FREE_ROOMS_SQL,
        {
            "room_type": room_type["room_type_id"],
            "check_in": query.check_in,
            "check_out": query.check_out,
        },
    )).mappings().all()

    return AvailabilityResult(
        room_type=room_type["room_type_name"],
        check_in=query.check_in,
        check_out=query.check_out,
        nights=query.nights,
        guests=query.guests,
        rooms_free=len(free),
        nile_view_free=sum(1 for room in free if room["view"] == "Nile"),
        rate_per_night=float(room_type["base_price"]),
        images=RoomImages(
            nile=room_type["image_nile"] or None,
            city=room_type["image_city"] or None,
        ),
    )