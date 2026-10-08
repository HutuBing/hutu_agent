"""skill_service 与 skill_api 测试（tmp_path 隔离磁盘，内存库）。"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

SKILL_MD = """---
name: echo_skill
description: "回声测试技能"
tags: [test]
---
你是回声技能：把收到的 task 原样返回。
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


def test_upload_version_delete(client, tmp_path):
    # v1
    r = client.post("/api/skills", files={"files": ("SKILL.md", SKILL_MD, "text/markdown")})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "echo_skill" and body["latest_version"] == 1
    sid = body["skill_id"]

    # 同名上传 → v2
    r = client.post("/api/skills", files={"files": ("SKILL.md", SKILL_MD, "text/markdown")})
    assert r.json()["skill_id"] == sid and r.json()["latest_version"] == 2

    # 版本内容
    r = client.get(f"/api/skills/{sid}/versions/1")
    assert r.status_code == 200
    assert "回声技能" in r.json()["body"]

    # 缺 SKILL.md → 400
    r = client.post("/api/skills", files={"files": ("other.txt", b"x", "text/plain")})
    assert r.status_code == 400

    # 删除：目录清空
    assert client.delete(f"/api/skills/{sid}").json() == {"ok": True}
    data_dir = tmp_path / "data" / "skills" / sid
    assert not data_dir.exists()
    assert client.get(f"/api/skills/{sid}").status_code == 404


def test_traversal_rejected(client):
    bad = SKILL_MD.replace("tags: [test]", "tags: [test]\nfiles: ['../evil.py']")
    r = client.post("/api/skills", files={"files": ("SKILL.md", bad, "text/markdown")})
    assert r.status_code == 400
