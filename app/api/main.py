import asyncio
import logging
import mimetypes
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.config import settings
from app.api.db import engine
from app.api.logging_config import setup_logging
from app.api.rate_limit import limiter, rate_limit_exceeded
from app.api.routers import (admin, auth, availability, bookings, calls, cancellations, changes, discounts, health,
                             hotel, my_bookings, payments, requests, staff)
from app.api.services.expiry import expiry_job
from scalar_fastapi import get_scalar_api_reference, Theme
setup_logging()
logger = logging.getLogger("hotel_api")

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@asynccontextmanager
async def lifespan(app: FastAPI):
    job = asyncio.create_task(expiry_job()) if settings.expiry_check_seconds > 0 else None
    yield
    if job:
        job.cancel()
        with suppress(asyncio.CancelledError):
            await job
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
app.include_router(auth.router)
app.include_router(my_bookings.router)
app.include_router(cancellations.router)
app.include_router(changes.router)
app.include_router(requests.router)
app.include_router(staff.router)
app.include_router(admin.router)
app.include_router(calls.router)
app.include_router(bookings.router)
app.include_router(payments.router)
mimetypes.add_type("image/webp", ".webp")
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "static"), name="static")


@app.get("/", tags=["Health"])
def root():
    return {"message": "Nile Pearl Hotel API is running"}


def openapi_schema():
    """The description /docs is drawn from. With DOCS_ONLY set, only those paths are listed;
    every endpoint still works, it is only left off the page (e.g. to show a few in a presentation)."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    shown = {path.strip() for path in settings.docs_only.split(",") if path.strip()}
    if shown:
        schema["paths"] = {path: operations for path, operations in schema["paths"].items() if path in shown}
    app.openapi_schema = schema
    return schema


app.openapi = openapi_schema
@app.get("/scalar", include_in_schema=False)
async def scalar_docs():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
        theme=Theme.MOON,
        dark_mode=True,
    )