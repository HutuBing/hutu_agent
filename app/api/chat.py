"""会话与对话 API。"""
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse as StreamingSSEResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker
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
    tool_calls_by_msg = await session_service.list_tool_calls(db, session_id)
    return [
        {
            "message_id": m.message_id,
            "role": m.role,
            "content": m.content,
            "create_time": str(m.create_time),
            # assistant 消息附工具调用记录（旧数据为空数组）
            "tool_calls": tool_calls_by_msg.get(m.message_id, []),
        }
        for m in items
    ]


async def _chat_stream(
    session_id: str,
    content: str,
    history: list[dict],
    request: Request,
    agent_ctx=None,
) -> AsyncIterator[str]:
    async def disconnected() -> bool:
        return await request.is_disconnected()

    full_reply = []
    cancelled = False
    tool_records: list[dict] = []  # 工具调用记录（按 run_id 配对 start/end）
    async for ev in run_chat_turn(
        content, history, request_disconnected=disconnected, agent_ctx=agent_ctx
    ):
        if ev.type == "delta":
            full_reply.append(ev.content)
        elif ev.type == "cancelled":
            cancelled = True
        elif ev.type == "tool_call_start":
            tool_records.append({
                "run_id": ev.run_id, "tool_name": ev.name,
                "args_json": ev.args_json, "status": "ok",
            })
        elif ev.type == "tool_call_end":
            rec = next(
                (r for r in reversed(tool_records)
                 if r["run_id"] == ev.run_id and "duration_ms" not in r),
                None,
            )
            if rec:
                rec.update(
                    duration_ms=ev.duration_ms,
                    output_preview=ev.output_preview,
                    status=ev.status,
                )
        yield _sse_encode(ev)

    # 事件流结束后统一落库（cancelled 时不落 assistant 残文与工具记录）
    from app.core.chat.session_service import add_message, add_tool_calls
    from app.db import get_engine

    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as db:
        await add_message(db, session_id, "user", content)
        if not cancelled and full_reply:
            msg = await add_message(db, session_id, "assistant", "".join(full_reply))
            completed = [r for r in tool_records if "duration_ms" in r]
            if completed:
                await add_tool_calls(db, msg.message_id, session_id, completed)


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
    # 请求作用域解析 Agent 上下文（LLM + 技能工具），事件流阶段不再碰 DB
    from app.core.agent.runtime import resolve_agent_context

    agent_ctx = await resolve_agent_context(db, s.agent_id)
    return StreamingSSEResponse(
        _chat_stream(session_id, req.content, history, request, agent_ctx)
    )
