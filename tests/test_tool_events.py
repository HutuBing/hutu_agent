"""工具调用事件测试：stub create_react_agent 按 scripted 顺序产出事件。"""
import pytest

from app.core.chat.chat_service import run_chat_turn
from app.core.chat.sse_events import (
    DeltaEvent,
    ErrorEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
)


class _StubAgent:
    """按脚本顺序 yield astream_events 形态的事件。"""

    def __init__(self, script):
        self._script = script

    def astream_events(self, _input, version="v2", config=None):
        async def gen():
            for ev in self._script:
                yield ev

        return gen()


@pytest.fixture
def no_fake(monkeypatch):
    monkeypatch.setenv("HUTU_LLM_FAKE", "0")
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _patch_agent(monkeypatch, script):
    # create_react_agent 在 chat_service 模块顶层 import → patch 该命名空间
    import app.core.chat.chat_service as cs

    monkeypatch.setattr(cs, "create_react_agent", lambda **kw: _StubAgent(script))


def _script():
    long_output = "x" * 800
    return [
        {"event": "on_chat_model_stream", "data": {"chunk": _Chunk("开始")}},
        {"event": "on_tool_start", "run_id": "r1", "name": "time_teller",
         "data": {"input": {"task": "查时间"}}},
        {"event": "on_tool_end", "run_id": "r1", "name": "time_teller",
         "data": {"output": _ToolMsg(long_output)}},
        {"event": "on_chat_model_stream", "data": {"chunk": _Chunk("现在是…")}},
        {"event": "on_chat_model_end", "data": {"output": _ModelOut(10, 20)}},
    ]


class _Chunk:
    def __init__(self, text):
        self._text = text

    def text(self):
        return self._text

    @property
    def content(self):
        return self._text


class _ToolMsg:
    def __init__(self, content):
        self.content = content


class _ModelOut:
    def __init__(self, pt, ct):
        self.usage_metadata = {"input_tokens": pt, "output_tokens": ct}


@pytest.mark.asyncio
async def test_tool_events_paired(no_fake, monkeypatch):
    _patch_agent(monkeypatch, _script())
    events = [ev async for ev in run_chat_turn("几点", [])]
    types = [ev.type for ev in events]

    # start 在 end 之前；事件序列合规
    assert "tool_call_start" in types and "tool_call_end" in types
    assert types.index("tool_call_start") < types.index("tool_call_end")

    start = next(ev for ev in events if isinstance(ev, ToolCallStartEvent))
    end = next(ev for ev in events if isinstance(ev, ToolCallEndEvent))
    assert start.run_id == end.run_id == "r1"
    assert start.name == end.name == "time_teller"
    assert '"task"' in start.args_json

    # output 截断 500 + usage 累加
    assert len(end.output_preview) == 501  # 500 + "…"
    usage = next(ev for ev in events if ev.type == "usage")
    assert usage.prompt_tokens == 10 and usage.completion_tokens == 20

    # delta 正文保留
    assert "开始" in "".join(ev.content for ev in events if isinstance(ev, DeltaEvent))


@pytest.mark.asyncio
async def test_tool_error_maps_to_error_status(no_fake, monkeypatch):
    script = [
        {"event": "on_tool_start", "run_id": "r2", "name": "s", "data": {"input": {}}},
        {"event": "on_tool_error", "run_id": "r2", "name": "s", "data": {"error": "boom"}},
    ]
    _patch_agent(monkeypatch, script)
    events = [ev async for ev in run_chat_turn("x", [])]
    end = next(ev for ev in events if isinstance(ev, ToolCallEndEvent))
    assert end.status == "error" and "boom" in end.output_preview
    # 无正文 → 空回复兜底
    assert any(ev.type == "error" and ev.code == "empty_response" for ev in events)
