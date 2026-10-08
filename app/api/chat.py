"""会话与对话 API。"""
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_dev_user, UserInfo
from app.core.chat import session_service
from app.core.chat.chat_service import run_chat_turn
from app.core.chat.sse_events import SSEEvent
from app.db import get_db

router = APIRouter(tags=["chat"])


class CreateSessionReq(BaseModel):
    agent_id: str = "default"
    title: str = ""


class ChatReq(BaseModel):
    content: str


def _sse_encode(ev: SSEEvent) -> str:
    return f"data: {ev.model_dump_json()}\n\n"


@router.post("/api/sessions")
async def create_session(
    req: CreateSessionReq,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(get_dev_user),
):
    s = await session_service.create_session(db, user.user_id, req.agent_id, req.title)
    return {"session_id": s.session_id, "agent_id": s.agent_id, "title": s.title}


@router.get("/api/sessions")
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(get_dev_user),
):
    items = await session_service.list_sessions(db, user.user_id)
    return [
        {
            "session_id": s.session_id,
            "agent_id": s.agent_id,
            "title": s.title,
            "create_time": str(s.create_time),
        }
        for s in items
    ]


@router.get("/api/sessions/{session_id}/messages")
async def list_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(get_dev_user),
):
    s = await session_service.get_session(db, session_id)
    if s is None or s.user_id != user.user_id:
        raise HTTPException(404, "session not found")
    items = await session_service.list_messages(db, session_id)
    return [
        {"message_id": m.message_id, "role": m.role, "content": m.content, "create_time": str(m.create_time)}
        for m in items
    ]


async def _chat_stream(
    session_id: str,
    content: str,
    history: list[dict],
    request: Request,
) -> AsyncIterator[str]:
    async def disconnected() -> bool:
        return await request.is_disconnected()

    full_reply = []
    cancelled = False
    async for ev in run_chat_turn(content, history, request_disconnected=disconnected):
        if ev.type == "delta":
            full_reply.append(ev.content)
        elif ev.type == "cancelled":
            cancelled = True
        yield _sse_encode(ev)

    # 事件流结束后统一落库（cancelled 时不落 assistant 残文）
    from app.core.chat.session_service import add_message
    from app.db import SessionLocal

    async with SessionLocal() as db:
        await add_message(db, session_id, "user", content)
        if not cancelled and full_reply:
            await add_message(db, session_id, "assistant", "".join(full_reply))


@router.post("/api/sessions/{session_id}/chat")
async def chat(
    session_id: str,
    req: ChatReq,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(get_dev_user),
):
    s = await session_service.get_session(db, session_id)
    if s is None or s.user_id != user.user_id:
        raise HTTPException(404, "session not found")

    history = [
        {"role": m.role, "content": m.content}
        for m in await session_service.list_messages(db, session_id)
    ]
    return StreamingSSEResponse(_chat_stream(session_id, req.content, history, request))


# 局部导入避免命名冲突：FastAPI 的 StreamingResponse
from fastapi.responses import StreamingResponse as StreamingSSEResponse  # noqa: E402
