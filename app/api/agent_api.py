"""Agent 管理 API。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import UserInfo, get_dev_user
from app.core.agent import agent_service
from app.db import get_db

router = APIRouter(tags=["agents"])


class AgentReq(BaseModel):
    name: str
    description: str = ""
    system_prompt: str = ""
    skill_ids: list[str] = []
    kb_ids: list[str] = []  # 挂载的知识库
    config_id: str | None = None  # None = 全局回退


@router.get("/api/agents")
async def list_agents(
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(get_dev_user),
):
    return [await agent_service.to_dict(db, a) for a in await agent_service.list_agents(db)]


@router.post("/api/agents", status_code=201)
async def create_agent(
    req: AgentReq,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(get_dev_user),
):
    try:
        agent = await agent_service.create_agent(
            db, user.user_id, req.name, req.description, req.system_prompt,
            req.skill_ids, req.config_id, req.kb_ids,
        )
    except agent_service.AgentServiceError as e:
        raise HTTPException(400, str(e))
    return await agent_service.to_dict(db, agent)


@router.get("/api/agents/{agent_id}")
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(get_dev_user),
):
    a = await agent_service.get_agent(db, agent_id)
    if a is None:
        raise HTTPException(404, "agent not found")
    return await agent_service.to_dict(db, a)


@router.put("/api/agents/{agent_id}")
async def update_agent(
    agent_id: str,
    req: AgentReq,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(get_dev_user),
):
    a = await agent_service.get_agent(db, agent_id)
    if a is None:
        raise HTTPException(404, "agent not found")
    try:
        a = await agent_service.update_agent(
            db, a, req.name, req.description, req.system_prompt,
            req.skill_ids, req.config_id, req.kb_ids
        )
    except agent_service.AgentServiceError as e:
        raise HTTPException(400, str(e))
    return await agent_service.to_dict(db, a)


@router.delete("/api/agents/{agent_id}")
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(get_dev_user),
):
    a = await agent_service.get_agent(db, agent_id)
    if a is None:
        raise HTTPException(404, "agent not found")
    await agent_service.delete_agent(db, a)
    return {"ok": True}
