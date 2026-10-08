"""agent_api 与绑定链路测试。"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

SKILL_MD = """---
name: echo_skill
description: "回声测试技能"
---
正文
"""


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HUTU_DB_URL", f"sqlite+aiosqlite:///{tmp_path/'t.db'}")
    monkeypatch.setenv("HUTU_SKILL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv(
        "HUTU_LLM_ENCRYPTION_KEY", "oB3FraRiZOzV17pIawHNDvEoW07MRJzps1aNlH4Cbww="
    )
    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def _setup_skill_and_llm(client):
    skill = client.post("/api/skills", files={"files": ("SKILL.md", SKILL_MD, "text/markdown")}).json()
    llm = client.post("/api/llm-configs", json={
        "name": "gw", "api_key": "sk-abcdef1234567890", "model_identifier": "m1",
    }).json()
    return skill["skill_id"], llm["config_id"]


def test_agent_crud_and_bindings(client):
    sid, cid = _setup_skill_and_llm(client)

    # 创建：绑定 1 技能 + 1 LLM
    r = client.post("/api/agents", json={
        "name": "测试Agent", "system_prompt": "你是测试。",
        "skill_ids": [sid], "config_id": cid,
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["skill_names"] == ["echo_skill"]
    assert body["llm_name"] == "gw"
    aid = body["agent_id"]

    # 更新：替换绑定（解绑 LLM → 全局回退）
    r = client.put(f"/api/agents/{aid}", json={
        "name": "测试Agent2", "skill_ids": [], "config_id": None,
    })
    assert r.status_code == 200
    assert r.json()["skill_ids"] == [] and r.json()["config_id"] is None

    # 删除 LLM 配置后 rel 级联（重新绑定再删）
    client.put(f"/api/agents/{aid}", json={"name": "t", "config_id": cid})
    client.delete(f"/api/llm-configs/{cid}")
    assert client.get(f"/api/agents/{aid}").json()["config_id"] is None

    # 删除 skill 后 rel 级联
    client.put(f"/api/agents/{aid}", json={"name": "t", "skill_ids": [sid]})
    client.delete(f"/api/skills/{sid}")
    assert client.get(f"/api/agents/{aid}").json()["skill_ids"] == []

    # 删除 agent
    assert client.delete(f"/api/agents/{aid}").json() == {"ok": True}
    assert client.get(f"/api/agents/{aid}").status_code == 404
