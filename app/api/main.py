import logging
import mimetypes
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.config import settings
from app.api.db import engine
from app.api.logging_config import setup_logging
from app.api.rate_limit import limiter, rate_limit_exceeded
from app.api.routers import availability, discounts, health, hotel

setup_logging()
logger = logging.getLogger("hotel_api")

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="Nile Pearl Hotel API", version="0.1.0", lifespan=lifespan)

# Rate limiting: added first, so it sits inside the logging middleware (a 429 is logged too)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded)
app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    client_ip = request.client.host if request.client else "-"

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "%s %s -> 500 (%.1f ms) from %s",
            request.method,
            request.url.path,
            duration_ms,
            client_ip,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Something went wrong on our side. Please try again later."},
        )

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %d (%.1f ms) from %s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        client_ip,
    )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(availability.router)
app.include_router(hotel.router)
app.include_router(discounts.router)
mimetypes.add_type("image/webp", ".webp")
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "static"), name="static")


@app.get("/", tags=["Health"])
def root():
    return {"message": "Nile Pearl Hotel API is running"}
