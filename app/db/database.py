from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

# Create our Async SQLAlchemy Engine
engine_args = {
    "echo": False,  # Set to True during debugging to print SQL queries to terminal
    "future": True,
}
if not settings.async_database_url.startswith("sqlite"):
    engine_args["pool_size"] = 10
    engine_args["max_overflow"] = 20

engine = create_async_engine(
    settings.async_database_url,
    **engine_args
)

# AsyncSession Dependency Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Critical for preventing detached instance errors after committing DB updates
    autocommit=False,
    autoflush=False
)

# Core mapping inheritance class for ALL database models
class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncSession:
    """
    FastAPI Dependency injected into routes.
    It guarantees safe lifecycle closure. Opens a pool slot -> runs query -> securely yields it back.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()