"""Agent 管理：CRUD 与技能/知识库/LLM 绑定。"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, AgentKbRel, AgentLlmRel, AgentSkillRel, KnowledgeBase, LlmConfig, Skill


class AgentServiceError(Exception):
    """Agent 业务错误（重名等）。"""


async def list_agents(db: AsyncSession) -> list[Agent]:
    result = await db.execute(select(Agent).order_by(Agent.update_time.desc()))
    return list(result.scalars())


async def get_agent(db: AsyncSession, agent_id: str) -> Agent | None:
    return (
        await db.execute(select(Agent).where(Agent.agent_id == agent_id))
    ).scalar_one_or_none()


async def create_agent(db: AsyncSession, user_id: str, name: str, description: str,
                       system_prompt: str, skill_ids: list[str],
                       config_id: str | None, kb_ids: list[str] | None = None) -> Agent:
    if not name.strip():
        raise AgentServiceError("Agent 名称不能为空")
    agent = Agent(
        agent_id=uuid.uuid4().hex,
        name=name.strip(),
        description=description,
        system_prompt=system_prompt,
        creator_user_id=user_id,
    )
    db.add(agent)
    await db.flush()
    await _set_bindings(db, agent.agent_id, skill_ids, config_id, kb_ids or [])
    await db.commit()
    await db.refresh(agent)  # 回填服务端生成的 update_time，避免序列化触发隐式 IO
    return agent


async def update_agent(db: AsyncSession, agent: Agent, name: str, description: str,
                       system_prompt: str, skill_ids: list[str],
                       config_id: str | None, kb_ids: list[str] | None = None) -> Agent:
    agent.name = name.strip()
    agent.description = description
    agent.system_prompt = system_prompt
    await _set_bindings(db, agent.agent_id, skill_ids, config_id, kb_ids or [])
    await db.commit()
    await db.refresh(agent)
    return agent


async def _set_bindings(db: AsyncSession, agent_id: str,
                        skill_ids: list[str], config_id: str | None,
                        kb_ids: list[str]) -> None:
    """事务内替换式绑定：先删旧再插新。"""
    for rel in (
        await db.execute(select(AgentSkillRel).where(AgentSkillRel.agent_id == agent_id))
    ).scalars():
        await db.delete(rel)
    for sid in skill_ids:
        db.add(AgentSkillRel(agent_id=agent_id, skill_id=sid))

    for rel in (
        await db.execute(select(AgentKbRel).where(AgentKbRel.agent_id == agent_id))
    ).scalars():
        await db.delete(rel)
    for kid in kb_ids:
        db.add(AgentKbRel(agent_id=agent_id, kb_id=kid))

    old = (
        await db.execute(select(AgentLlmRel).where(AgentLlmRel.agent_id == agent_id))
    ).scalar_one_or_none()
    if old is not None:
        await db.delete(old)
    if config_id:  # None/空 = 全局回退
        db.add(AgentLlmRel(agent_id=agent_id, config_id=config_id))


async def delete_agent(db: AsyncSession, agent: Agent) -> None:
    for rel in (
        await db.execute(select(AgentSkillRel).where(AgentSkillRel.agent_id == agent.agent_id))
    ).scalars():
        await db.delete(rel)
    for rel in (
        await db.execute(select(AgentKbRel).where(AgentKbRel.agent_id == agent.agent_id))
    ).scalars():
        await db.delete(rel)
    rel = (
        await db.execute(select(AgentLlmRel).where(AgentLlmRel.agent_id == agent.agent_id))
    ).scalar_one_or_none()
    if rel is not None:
        await db.delete(rel)
    await db.delete(agent)
    await db.commit()


async def get_bound_skill_ids(db: AsyncSession, agent_id: str) -> list[str]:
    result = await db.execute(
        select(AgentSkillRel.skill_id).where(AgentSkillRel.agent_id == agent_id)
    )
    return list(result.scalars())


async def get_bound_kb_ids(db: AsyncSession, agent_id: str) -> list[str]:
    result = await db.execute(
        select(AgentKbRel.kb_id).where(AgentKbRel.agent_id == agent_id)
    )
    return list(result.scalars())


async def get_bound_config_id(db: AsyncSession, agent_id: str) -> str | None:
    rel = (
        await db.execute(select(AgentLlmRel).where(AgentLlmRel.agent_id == agent_id))
    ).scalar_one_or_none()
    return rel.config_id if rel else None


async def to_dict(db: AsyncSession, a: Agent) -> dict:
    """聚合序列化：附绑定的技能名、知识库名与 LLM 名。"""
    skill_names = (
        await db.execute(
            select(Skill.name).join(AgentSkillRel, AgentSkillRel.skill_id == Skill.skill_id)
            .where(AgentSkillRel.agent_id == a.agent_id)
        )
    ).scalars()
    kb_names = (
        await db.execute(
            select(KnowledgeBase.name).join(AgentKbRel, AgentKbRel.kb_id == KnowledgeBase.kb_id)
            .where(AgentKbRel.agent_id == a.agent_id)
        )
    ).scalars()
    llm_name = None
    config_id = await get_bound_config_id(db, a.agent_id)
    if config_id:
        llm_name = (
            await db.execute(
                select(LlmConfig.name).where(LlmConfig.config_id == config_id)
            )
        ).scalar_one_or_none()
    return {
        "agent_id": a.agent_id,
        "name": a.name,
        "description": a.description,
        "system_prompt": a.system_prompt,
        "skill_ids": await get_bound_skill_ids(db, a.agent_id),
        "skill_names": list(skill_names),
        "kb_ids": await get_bound_kb_ids(db, a.agent_id),
        "kb_names": list(kb_names),
        "config_id": config_id,
        "llm_name": llm_name,
        "update_time": str(a.update_time),
    }
