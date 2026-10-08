"""应用入口。"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.config import get_settings
from app.models import Base
from app.db import engine
from app.api.chat import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # MVP：建表交给 metadata；后续切 Alembic
    yield
    await engine.dispose()


app = FastAPI(title="hutu-agent", version="0.1.0-mvp", lifespan=lifespan)
app.include_router(chat_router)


@app.get("/health")
async def health():
    return {"status": "ok", "llm_fake": get_settings().llm_fake}


@app.get("/")
async def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")
