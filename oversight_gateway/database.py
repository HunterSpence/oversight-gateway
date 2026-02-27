"""Async database connection and session management"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
import structlog

logger = structlog.get_logger()

Base = declarative_base()

# Global engine and session maker
_engine = None
_async_session_maker = None


def init_db(database_url: str) -> None:
    """
    Initialize async database engine and session maker.
    
    Args:
        database_url: Async database URL (e.g., "sqlite+aiosqlite:///./oversight_gateway.db")
    """
    global _engine, _async_session_maker
    
    logger.info("initializing_database", url=database_url)
    
    _engine = create_async_engine(
        database_url,
        echo=False,
        future=True,
    )
    
    _async_session_maker = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    logger.info("database_initialized")


async def create_tables() -> None:
    """Create all database tables"""
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    logger.info("creating_tables")
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("tables_created")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database session.
    
    Usage:
        @app.get("/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    if _async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    async with _async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def close_db() -> None:
    """Close database connection"""
    global _engine
    if _engine:
        logger.info("closing_database")
        await _engine.dispose()
        logger.info("database_closed")
