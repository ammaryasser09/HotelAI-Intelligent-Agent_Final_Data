from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.db import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health(db: AsyncConnection = Depends(get_db)):
    result = await db.execute(
        text("SELECT hotel_today() AS today, (SELECT count(*) FROM rooms) AS rooms")
    )
    row = result.one()
    return {
        "status": "ok",
        "database": "connected",
        "hotel_today": str(row.today),
        "rooms": row.rooms,
    }
