from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.db import get_db
from app.api.schemas.hotel import HotelPhoto, Menu, MenuItem, RoomType

router = APIRouter(tags=["Hotel"])

ROOM_TYPES_SQL = text("""
    SELECT room_type_id, room_type_name, description, capacity, base_price, size_sqm, image_nile, image_city
    FROM room_types
    ORDER BY base_price
""")

# queries.sql 13
HOTEL_PHOTOS_SQL = text("""
    SELECT photo_key, title_en, title_ar, image_path
    FROM hotel_photos
    WHERE CAST(:photo_key AS text) IS NULL OR photo_key = lower(CAST(:photo_key AS text))
    ORDER BY photo_key
""")

# queries.sql 7
MENU_SQL = text("""
    SELECT item_id, name_en, name_ar, category, price, dietary
    FROM menu_items
    WHERE (NOT :night_only OR night_menu)
      AND (CAST(:category AS text) IS NULL OR lower(category) = lower(CAST(:category AS text)))
    ORDER BY category, price
""")
DELIVERY_CHARGE_SQL = text("SELECT price FROM services WHERE service_id = 'S002'")


@router.get("/room-types", response_model=list[RoomType])
async def list_room_types(db: AsyncConnection = Depends(get_db)):
    rows = (await db.execute(ROOM_TYPES_SQL)).mappings().all()
    return [RoomType(**row) for row in rows]


@router.get("/hotel-photos", response_model=list[HotelPhoto])
async def list_hotel_photos(photo_key: str | None = None, db: AsyncConnection = Depends(get_db)):
    rows = (await db.execute(HOTEL_PHOTOS_SQL, {"photo_key": photo_key})).mappings().all()
    if photo_key and not rows:
        keys = (await db.execute(text("SELECT photo_key FROM hotel_photos ORDER BY photo_key"))).scalars().all()
        raise HTTPException(status_code=404, detail={"reason": "PHOTO_NOT_FOUND", "photo_keys": keys})
    return [HotelPhoto(**row) for row in rows]


@router.get("/menu", response_model=Menu)
async def get_menu(night_only: bool = False, category: str | None = None, db: AsyncConnection = Depends(get_db)):
    rows = (await db.execute(MENU_SQL, {"night_only": night_only, "category": category})).mappings().all()
    delivery_charge = (await db.execute(DELIVERY_CHARGE_SQL)).scalar_one()
    return Menu(items=[MenuItem(**row) for row in rows], delivery_charge=float(delivery_charge))
