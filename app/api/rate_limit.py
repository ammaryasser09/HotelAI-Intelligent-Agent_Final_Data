from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.config import settings

# Every endpoint gets the default limit; a route can set a stricter one with @limiter.limit("5/minute")
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])


async def rate_limit_exceeded(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": {"reason": "TOO_MANY_REQUESTS", "limit": str(exc.detail)}},
    )
