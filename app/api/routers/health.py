from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.api.db import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
def health(db: Connection = Depends(get_db)):
    row = db.execute(
        text("SELECT hotel_today() AS today, (SELECT count(*) FROM rooms) AS rooms")
    ).one()
    return {
        "status": "ok",
        "database": "connected",
        "hotel_today": str(row.today),
        "rooms": row.rooms,
    }