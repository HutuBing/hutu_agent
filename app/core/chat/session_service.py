"""会话与消息的数据访问。"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message, Session


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
