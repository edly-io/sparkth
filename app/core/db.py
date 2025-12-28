from collections.abc import AsyncGenerator, Generator

from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import Session, create_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)

# Create async engine for async operations
async_engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False,
    pool_pre_ping=True,
)
async_session_maker = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)


def get_engine() -> Engine:
    return engine


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
