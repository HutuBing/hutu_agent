"""LLM 配置 API 测试（TestClient + 内存库）。"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HUTU_DB_URL", f"sqlite+aiosqlite:///{tmp_path/'t.db'}")
    monkeypatch.setenv(
        "HUTU_LLM_ENCRYPTION_KEY", "oB3FraRiZOzV17pIawHNDvEoW07MRJzps1aNlH4Cbww="
    )
    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app) as c:  # context manager 触发 lifespan 建表
        yield c
    get_settings.cache_clear()


def _payload(**over):
    p = {
        "name": "fuyao-gw",
        "api_base_url": "https://gw.example/v1",
        "api_key": "sk-abcdef1234567890",
        "model_identifier": "fuyao-coding",
    }
    p.update(over)
    return p


def test_crud_and_mask(client):
    # 创建
    r = client.post("/api/llm-configs", json=_payload())
    assert r.status_code == 201
    body = r.json()
    assert body["api_key_masked"] == "sk-****7890"

    # 列表：绝无明文/密文
    r = client.get("/api/llm-configs")
    raw = r.text
    assert "sk-abcdef1234567890" not in raw
    assert "api_key_encrypted" not in raw
    assert len(r.json()) == 1

    # 重名 400
    assert client.post("/api/llm-configs", json=_payload()).status_code == 400

    # 更新：api_key 留空 = 保留旧 key
    cid = body["config_id"]
    r = client.put(f"/api/llm-configs/{cid}", json=_payload(name="fuyao-2", api_key=""))
    assert r.status_code == 200
    assert r.json()["api_key_masked"] == "sk-****7890"  # 旧 key 的掩码
    assert r.json()["name"] == "fuyao-2"

    # 更新：填新 key → 掩码变化
    r = client.put(f"/api/llm-configs/{cid}", json=_payload(name="fuyao-2", api_key="sk-zzzzzzzz9999"))
    assert r.json()["api_key_masked"] == "sk-****9999"

    # 删除 + 404
    assert client.delete(f"/api/llm-configs/{cid}").json() == {"ok": True}
    assert client.delete(f"/api/llm-configs/{cid}").status_code == 404
