"""应用入口。"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.models import Base
from app.db import get_engine, reset_engine
from app.api.chat import router as chat_router
from app.api.llm_api import router as llm_router
from app.api.skill_api import router as skill_router
from app.api.agent_api import router as agent_router
from app.api.kb_api import router as kb_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    reset_engine()  # 支持测试进程内切换 DB URL
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # MVP：建表交给 metadata；后续切 Alembic
        await _ensure_columns(conn)
    yield
    await engine.dispose()


async def _ensure_columns(conn) -> None:
    """老库补列：create_all 不会 ALTER 已有表，这里幂等补齐新增列（SQLite）。"""
    from sqlalchemy import text

    cols = [r[1] for r in (await conn.exec_driver_sql("PRAGMA table_info(llm_config)")).fetchall()]
    if cols and "usage" not in cols:
        await conn.exec_driver_sql(
            "ALTER TABLE llm_config ADD COLUMN usage VARCHAR(16) DEFAULT 'chat' NOT NULL"
        )


app = FastAPI(title="hutu-agent", version="0.3.0", lifespan=lifespan)
app.include_router(chat_router)
app.include_router(llm_router)
app.include_router(skill_router)
app.include_router(agent_router)
app.include_router(kb_router)


@app.get("/health")
async def health():
    return {"status": "ok", "llm_fake": get_settings().llm_fake}


# 静态托管放在所有 API 路由之后（Starlette 按注册顺序匹配，/api、/health 优先命中）
_WEB_DIST = Path(__file__).parent.parent / "web" / "dist"
if _WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=_WEB_DIST, html=True), name="web")
else:
    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(Path(__file__).parent / "static" / "index.html")
