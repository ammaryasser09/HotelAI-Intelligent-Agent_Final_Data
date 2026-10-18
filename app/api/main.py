import mimetypes
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.config import settings
from app.api.routers import health

PROJECT_ROOT = Path(__file__).resolve().parents[2]

app = FastAPI(title="Nile Pearl Hotel API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
mimetypes.add_type("image/webp", ".webp")
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "static"), name="static")


@app.get("/", tags=["Health"])
def root():
    return {"message": "Nile Pearl Hotel API is running"}