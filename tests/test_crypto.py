"""crypto 模块测试。"""
import pytest

from app.core.llm.crypto import (
    EncryptionKeyError,
    decrypt_api_key,
    encrypt_api_key,
    mask_key,
)


@pytest.fixture
def key_env(monkeypatch):
    monkeypatch.setenv("HUTU_LLM_ENCRYPTION_KEY", "oB3FraRiZOzV17pIawHNDvEoW07MRJzps1aNlH4Cbww=")
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_roundtrip(key_env):
    token = encrypt_api_key("sk-secret-123")
    assert token != "sk-secret-123"
    assert decrypt_api_key(token) == "sk-secret-123"


def test_mask():
    assert mask_key("sk-abcdefghijklmnop") == "sk-****mnop"
    assert mask_key("short") == "****"


def test_missing_key(monkeypatch):
    monkeypatch.delenv("HUTU_LLM_ENCRYPTION_KEY", raising=False)
    # .env 文件里配置了该 key，需屏蔽 env_file 读取才能模拟"未配置"
    from app.config import Settings, get_settings

    monkeypatch.setattr(
        Settings, "model_config", {**Settings.model_config, "env_file": None}
    )
    get_settings.cache_clear()
    with pytest.raises(EncryptionKeyError):
        encrypt_api_key("x")
    get_settings.cache_clear()


def test_wrong_key(monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("HUTU_LLM_ENCRYPTION_KEY", Fernet.generate_key().decode())
    from app.config import get_settings

    get_settings.cache_clear()
    token = encrypt_api_key("sk-secret")
    # 换一把密钥解密 → 报错
    monkeypatch.setenv("HUTU_LLM_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    with pytest.raises(EncryptionKeyError):
        decrypt_api_key(token)
    get_settings.cache_clear()
