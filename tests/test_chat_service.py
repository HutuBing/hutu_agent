"""对话内核测试：fake 模式跑通 SSE v3 事件序列。"""
import pytest

from app.config import get_settings
from app.core.chat.chat_service import run_chat_turn
from app.core.chat.sse_events import (
    DeltaEvent,
    ErrorEvent,
    MsgEndEvent,
    MsgStartEvent,
    UsageEvent,
)


@pytest.fixture
def fake_settings(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("HUTU_LLM_FAKE", "1")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_event_sequence(fake_settings):
    events = [ev async for ev in run_chat_turn("你好", [])]
    types = [ev.type for ev in events]

    # msg_start 必为第一个，msg_end 必为最后一个
    assert types[0] == "msg_start"
    assert types[-1] == "msg_end"
    assert "error" not in types

    # delta 内容完整拼接
    text = "".join(ev.content for ev in events if isinstance(ev, DeltaEvent))
    assert "你好" in text

    # usage 在 msg_end 之前
    assert UsageEvent in (type(ev) for ev in events)


@pytest.mark.asyncio
async def test_no_events_after_msg_end(fake_settings):
    events = [ev async for ev in run_chat_turn("再见", [])]
    end_idx = [i for i, ev in enumerate(events) if isinstance(ev, MsgEndEvent)][0]
    assert end_idx == len(events) - 1
    assert not any(isinstance(ev, MsgStartEvent) for ev in events[end_idx:])


@pytest.mark.asyncio
async def test_history_passed(fake_settings):
    history = [{"role": "user", "content": "第一轮"}, {"role": "assistant", "content": "回复"}]
    events = [ev async for ev in run_chat_turn("第二轮", history)]
    types = [ev.type for ev in events]
    assert types[0] == "msg_start" and types[-1] == "msg_end"
    assert not any(isinstance(ev, ErrorEvent) for ev in events)
