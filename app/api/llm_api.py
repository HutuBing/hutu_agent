"""LLM 配置管理 API。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import UserInfo, get_dev_user
from app.core.llm import llm_service
from app.core.llm.crypto import EncryptionKeyError
from app.db import get_db

router = APIRouter(tags=["llm"])


class LlmConfigReq(BaseModel):
    name: str
    provider: str = "openai_compatible"
    api_base_url: str = ""
    api_key: str = ""  # create 必填；update 留空 = 不修改
    model_identifier: str = ""
    usage: str = "chat"  # chat=对话模型 / embedding=向量化模型
    price_per_1k_tokens: float = 0.0
    quota_limit: int = 0
    status: str = "enabled"


@router.get("/api/llm-configs")
async def list_configs(
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(get_dev_user),
):
    return [llm_service.to_dict(c) for c in await llm_service.list_configs(db)]


@router.post("/api/llm-configs", status_code=201)
async def create_config(
    req: LlmConfigReq,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(get_dev_user),
):
    try:
        cfg = await llm_service.create_config(db, user.user_id, **req.model_dump())
    except llm_service.LlmConfigError as e:
        raise HTTPException(400, str(e))
    except EncryptionKeyError as e:
        raise HTTPException(500, str(e))
    return llm_service.to_dict(cfg)


@router.put("/api/llm-configs/{config_id}")
async def update_config(
    config_id: str,
    req: LlmConfigReq,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(get_dev_user),
):
    cfg = await llm_service.get_config(db, config_id)
    if cfg is None:
        raise HTTPException(404, "llm config not found")
    try:
        cfg = await llm_service.update_config(db, cfg, **req.model_dump())
    except llm_service.LlmConfigError as e:
        raise HTTPException(400, str(e))
    except EncryptionKeyError as e:
        raise HTTPException(500, str(e))
    return llm_service.to_dict(cfg)


@router.delete("/api/llm-configs/{config_id}")
async def delete_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(get_dev_user),
):
    cfg = await llm_service.get_config(db, config_id)
    if cfg is None:
        raise HTTPException(404, "llm config not found")
    await llm_service.delete_config(db, cfg)
    return {"ok": True}
