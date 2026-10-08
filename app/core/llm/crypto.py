"""Fernet 对称加密封装（LLM API Key 落库加密 / 脱敏展示）。

密钥从 HUTU_LLM_ENCRYPTION_KEY 环境变量读取，不落库、不进日志。
生成方式：python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class EncryptionKeyError(Exception):
    """加密密钥缺失或与存储时不一致。"""


def _fernet() -> Fernet:
    key = get_settings().llm_encryption_key
    if not key:
        raise EncryptionKeyError(
            "未配置 HUTU_LLM_ENCRYPTION_KEY，请在 .env 中设置（Fernet.generate_key() 生成）"
        )
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as e:
        raise EncryptionKeyError(f"HUTU_LLM_ENCRYPTION_KEY 不是合法的 Fernet 密钥: {e}") from e


def encrypt_api_key(plain: str) -> str:
    """明文 → Fernet 密文（base64 字符串，落库用）。"""
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_api_key(token: str) -> str:
    """密文 → 明文。密钥与加密时不一致会抛 EncryptionKeyError。"""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise EncryptionKeyError(
            "解密失败：加密密钥与存储时不一致，请重新录入 API Key"
        ) from e


def mask_key(plain: str) -> str:
    """明文 → sk-****abcd 形式；明文过短时全部掩码。"""
    if len(plain) < 8:
        return "****"
    return f"sk-****{plain[-4:]}"
