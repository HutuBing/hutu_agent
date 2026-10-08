"""会话与消息的数据访问。"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message, MessageToolCall, Session


async def create_session(db: AsyncSession, user_id: str, agent_id: str = "default", title: str = "") -> Session:
    s = Session(session_id=uuid.uuid4().hex, agent_id=agent_id, user_id=user_id, title=title)
    db.add(s)
    await db.commit()
    return s


async def get_session(db: AsyncSession, session_id: str) -> Session | None:
    return (
        await db.execute(select(Session).where(Session.session_id == session_id))
    ).scalar_one_or_none()


async def list_sessions(db: AsyncSession, user_id: str) -> list[Session]:
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user_id)
        .order_by(Session.create_time.desc())
    )
    return list(result.scalars())


async def list_messages(db: AsyncSession, session_id: str, limit: int = 50) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.create_time.asc(), Message.id.asc())
        .limit(limit)
    )
    return list(result.scalars())


async def add_message(db: AsyncSession, session_id: str, role: str, content: str) -> Message:
    m = Message(message_id=uuid.uuid4().hex, session_id=session_id, role=role, content=content)
    db.add(m)
    await db.commit()
    return m


async def add_tool_calls(db: AsyncSession, message_id: str, session_id: str,
                         records: list[dict]) -> None:
    """批量写入某条 assistant 消息期间的工具调用记录。"""
    for r in records:
        db.add(MessageToolCall(
            message_id=message_id,
            session_id=session_id,
            tool_name=r["tool_name"],
            args_json=r.get("args_json", ""),
            output_preview=r.get("output_preview", ""),
            status=r.get("status", "ok"),
            duration_ms=r.get("duration_ms", 0),
        ))
    await db.commit()


async def list_tool_calls(db: AsyncSession, session_id: str) -> dict[str, list[dict]]:
    """按 message_id 分组返回会话内全部工具调用记录。"""
    result = await db.execute(
        select(MessageToolCall)
        .where(MessageToolCall.session_id == session_id)
        .order_by(MessageToolCall.id.asc())
    )
    grouped: dict[str, list[dict]] = {}
    for tc in result.scalars():
        grouped.setdefault(tc.message_id, []).append({
            "tool_name": tc.tool_name,
            "args_json": tc.args_json,
            "output_preview": tc.output_preview,
            "status": tc.status,
            "duration_ms": tc.duration_ms,
        })
    return grouped
