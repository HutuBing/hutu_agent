"""应用入口。"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.config import get_settings
from app.models import Base
from app.db import get_engine, reset_engine
from app.api.chat import router as chat_router
from app.api.llm_api import router as llm_router
from app.api.skill_api import router as skill_router
from app.api.agent_api import router as agent_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    reset_engine()  # 支持测试进程内切换 DB URL
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # MVP：建表交给 metadata；后续切 Alembic
    yield
    await engine.dispose()


app = FastAPI(title="hutu-agent", version="0.2.0", lifespan=lifespan)
app.include_router(chat_router)
app.include_router(llm_router)
app.include_router(skill_router)
app.include_router(agent_router)


@app.get("/health")
async def health():
    return {"status": "ok", "llm_fake": get_settings().llm_fake}


@app.get("/")
async def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")
