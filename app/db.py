"""SQLAlchemy async 引擎与 Session 工厂（惰性创建，支持测试时切换 DB URL）。"""
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """首次访问时按当前 settings 创建引擎；之后复用。"""
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().db_url, echo=False)
    return _engine


def reset_engine() -> None:
    """测试用：清空缓存的引擎，下次 get_engine() 按新 settings 重建。"""
    global _engine
    _engine = None


async def get_db() -> AsyncSession:
    """FastAPI 依赖：每请求一个 Session。"""
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        yield session
