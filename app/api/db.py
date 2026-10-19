from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.api.config import settings

async_database_url = make_url(settings.database_url).set(drivername="postgresql+asyncpg")

engine = create_async_engine(
    async_database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)


async def get_db():
    async with engine.connect() as connection:
        yield connection