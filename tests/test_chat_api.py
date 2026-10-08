"""对话 API + 工具调用落库测试。"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


class _StubAgent:
    def __init__(self, script):
        self._script = script

    def astream_events(self, _input, version="v2", config=None):
        async def gen():
            for ev in self._script:
                yield ev

        return gen()


def _script():
    return [
        {"event": "on_tool_start", "run_id": "r1", "name": "time_teller",
         "data": {"input": {"task": "查时间"}}},
        {"event": "on_tool_end", "run_id": "r1", "name": "time_teller",
         "data": {"output": "2026-10-08 17:00 星期四"}},
        {"event": "on_chat_model_stream", "data": {"chunk": _C("现在是 17:00")}},
        {"event": "on_chat_model_end", "data": {"output": _M(5, 10)}},
    ]


class _C:
    def __init__(self, t):
        self._t = t

    def text(self):
        return self._t

    @property
    def content(self):
        return self._t


class _M:
    def __init__(self, pt, ct):
        self.usage_metadata = {"input_tokens": pt, "output_tokens": ct}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HUTU_DB_URL", f"sqlite+aiosqlite:///{tmp_path/'t.db'}")
    monkeypatch.setenv("HUTU_LLM_FAKE", "0")
    import app.core.chat.chat_service as cs

    monkeypatch.setattr(cs, "create_react_agent", lambda **kw: _StubAgent(_script()))
    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def _read_sse(resp):
    events = []
    for line in resp.text.split("\n"):
        if line.startswith("data: "):
            import json

            events.append(json.loads(line[6:]))
    return events


def test_tool_calls_persisted_and_returned(client):
    sid = client.post("/api/sessions", json={"title": "t"}).json()["session_id"]
    r = client.post(f"/api/sessions/{sid}/chat", json={"content": "现在几点了"})
    assert r.status_code == 200
    events = _read_sse(r)
    assert any(e["type"] == "tool_call_start" for e in events)
    assert any(e["type"] == "tool_call_end" for e in events)

    msgs = client.get(f"/api/sessions/{sid}/messages").json()
    assistant = [m for m in msgs if m["role"] == "assistant"]
    assert len(assistant) == 1
    tcs = assistant[0]["tool_calls"]
    assert len(tcs) == 1
    assert tcs[0]["tool_name"] == "time_teller"
    assert "task" in tcs[0]["args_json"]
    assert "星期四" in tcs[0]["output_preview"]
    assert tcs[0]["status"] == "ok"

    # user 消息无 tool_calls
    user_msgs = [m for m in msgs if m["role"] == "user"]
    assert all(m["tool_calls"] == [] for m in user_msgs)
