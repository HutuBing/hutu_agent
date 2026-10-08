"""LLM 配置管理：CRUD 与加密编排。

API Key 只在 create/update 时接触明文，落库前加密；对外只暴露脱敏形式。
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm.crypto import decrypt_api_key, encrypt_api_key, mask_key
from app.models import AgentLlmRel, LlmConfig


class LlmConfigError(Exception):
    """配置业务错误（重名等）。"""


async def list_configs(db: AsyncSession) -> list[LlmConfig]:
    result = await db.execute(select(LlmConfig).order_by(LlmConfig.create_time.desc()))
    return list(result.scalars())


async def get_config(db: AsyncSession, config_id: str) -> LlmConfig | None:
    return (
        await db.execute(select(LlmConfig).where(LlmConfig.config_id == config_id))
    ).scalar_one_or_none()


async def create_config(db: AsyncSession, user_id: str, **fields) -> LlmConfig:
    plain_key = fields.pop("api_key")
    if not plain_key:
        raise LlmConfigError("api_key 不能为空")
    name = fields["name"]
    if await _name_exists(db, name):
        raise LlmConfigError(f"配置名已存在: {name}")
    cfg = LlmConfig(
        config_id=uuid.uuid4().hex,
        api_key_encrypted=encrypt_api_key(plain_key),
        creator_user_id=user_id,
        **fields,
    )
    db.add(cfg)
    await db.commit()
    return cfg


async def update_config(db: AsyncSession, cfg: LlmConfig, **fields) -> LlmConfig:
    plain_key = fields.pop("api_key", None)
    if plain_key:  # 留空 = 保留旧密文
        cfg.api_key_encrypted = encrypt_api_key(plain_key)
    new_name = fields.get("name")
    if new_name and new_name != cfg.name and await _name_exists(db, new_name):
        raise LlmConfigError(f"配置名已存在: {new_name}")
    for k, v in fields.items():
        setattr(cfg, k, v)
    await db.commit()
    return cfg


async def delete_config(db: AsyncSession, cfg: LlmConfig) -> None:
    # 级联清理绑定关系
    rels = (
        await db.execute(select(AgentLlmRel).where(AgentLlmRel.config_id == cfg.config_id))
    ).scalars()
    for rel in rels:
        await db.delete(rel)
    await db.delete(cfg)
    await db.commit()


def to_dict(cfg: LlmConfig) -> dict:
    """对外序列化：只含脱敏 key，绝不含密文或明文。"""
    masked = "****"
    if cfg.api_key_encrypted:
        try:
            masked = mask_key(decrypt_api_key(cfg.api_key_encrypted))
        except Exception:  # noqa: BLE001 — key 丢失时仍要能展示列表
            masked = "****（解密失败）"
    return {
        "config_id": cfg.config_id,
        "name": cfg.name,
        "provider": cfg.provider,
        "api_base_url": cfg.api_base_url,
        "model_identifier": cfg.model_identifier,
        "api_key_masked": masked,
        "price_per_1k_tokens": cfg.price_per_1k_tokens,
        "quota_limit": cfg.quota_limit,
        "status": cfg.status,
        "create_time": str(cfg.create_time),
    }


async def _name_exists(db: AsyncSession, name: str) -> bool:
    return (
        await db.execute(select(LlmConfig).where(LlmConfig.name == name))
    ).scalar_one_or_none() is not None
