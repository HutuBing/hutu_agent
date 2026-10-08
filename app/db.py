"""SQLAlchemy async 引擎与 Session 工厂。"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

engine = create_async_engine(get_settings().db_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """FastAPI 依赖：每请求一个 Session。"""
    async with SessionLocal() as session:
        yield session
