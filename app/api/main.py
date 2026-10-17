from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.api.db import get_db

app = FastAPI(title="Nile Pearl Hotel API", version="0.1.0")


@app.get("/")
def root():
    return {"message": "Nile Pearl Hotel API is running"}


@app.get("/health")
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