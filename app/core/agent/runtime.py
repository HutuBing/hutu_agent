"""对话运行时装配：按会话的 Agent 解析 LLM 与技能工具。

DB 解析在请求作用域完成；事件流阶段只使用纯内存对象（与 chat_service 的既有模式一致）。
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime

from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.agent import agent_service
from app.core.llm.crypto import EncryptionKeyError, decrypt_api_key
from app.models import LlmConfig, Skill

logger = logging.getLogger(__name__)


@dataclass
class LlmSpec:
    base_url: str
    api_key: str
    model: str


@dataclass
class SkillInfo:
    name: str
    description: str
    body: str
    skill_id: str = ""
    version: int = 1
    has_handler: bool = False  # 技能目录含 handler.py（run(task, context) -> str）


@dataclass
class AgentChatContext:
    agent_id: str
    system_prompt: str
    llm: LlmSpec | None = None
    skills: list[SkillInfo] = field(default_factory=list)
    skipped_skills: list[str] = field(default_factory=list)  # 读盘失败被跳过的技能名


async def resolve_agent_context(db: AsyncSession, agent_id: str) -> AgentChatContext | None:
    """解析会话绑定的 Agent；default 或不存在 → None（全局回退）。"""
    if agent_id == "default":
        return None
    agent = await agent_service.get_agent(db, agent_id)
    if agent is None:
        logger.warning("会话绑定的 agent 不存在: %s，回退全局配置", agent_id)
        return None

    ctx = AgentChatContext(
        agent_id=agent.agent_id,
        system_prompt=agent.system_prompt or get_settings().agent_system_prompt,
    )

    # LLM：绑定配置 → 全局回退；解密失败也回退并告警
    config_id = await agent_service.get_bound_config_id(db, agent.agent_id)
    if config_id:
        cfg = (
            await db.execute(select(LlmConfig).where(LlmConfig.config_id == config_id))
        ).scalar_one_or_none()
        if cfg is not None and cfg.status == "enabled":
            try:
                ctx.llm = LlmSpec(
                    base_url=cfg.api_base_url,
                    api_key=decrypt_api_key(cfg.api_key_encrypted),
                    model=cfg.model_identifier,
                )
            except EncryptionKeyError as e:
                logger.warning("Agent %s 绑定的 LLM 解密失败，回退全局配置: %s", agent_id, e)

    # Skills：读盘失败的跳过，不炸对话
    for sid in await agent_service.get_bound_skill_ids(db, agent.agent_id):
        skill = (
            await db.execute(select(Skill).where(Skill.skill_id == sid))
        ).scalar_one_or_none()
        if skill is None:
            continue
        try:
            from app.core.skill import skill_service

            meta = skill_service.read_skill_meta(skill.skill_id, skill.latest_version)
            has_handler = skill_service.load_handler(skill.skill_id, skill.latest_version) is not None
        except Exception:  # noqa: BLE001
            logger.warning("技能 %s 正文读取失败，跳过", sid, exc_info=True)
            ctx.skipped_skills.append(skill.name)
            continue
        ctx.skills.append(SkillInfo(
            name=skill.name, description=skill.description, body=meta.body,
            skill_id=skill.skill_id, version=skill.latest_version, has_handler=has_handler,
        ))

    return ctx


def build_chat_model(spec: LlmSpec | None) -> ChatOpenAI:
    """绑定配置优先，否则回退 .env 全局配置。"""
    s = get_settings()
    if spec is not None:
        return ChatOpenAI(
            model=spec.model,
            api_key=spec.api_key,
            base_url=spec.base_url or None,
            streaming=True,
        )
    return ChatOpenAI(
        model=s.llm_model,
        api_key=s.llm_api_key,
        base_url=s.llm_base_url or None,
        streaming=True,
    )


class _SkillArgs(BaseModel):
    task: str = Field(description="交给该技能处理的任务描述")


def build_skill_tools(ctx: AgentChatContext, llm: ChatOpenAI) -> list[StructuredTool]:
    """每个技能 = 一个工具。

    无 handler：一次无工具子 Agent 调用（概设：Skill → LangChain Tool）。
    有 handler.py：先执行 handler 获取真实数据，再把数据+任务交给子 Agent 生成回复。
    """
    tools = []
    for sk in ctx.skills:
        async def _run(task: str, _sk=sk, _llm=llm) -> str:
            from langchain_core.messages import HumanMessage
            from langgraph.prebuilt import create_react_agent
            from app.core.skill import skill_service

            handler_result = ""
            if _sk.has_handler:
                try:
                    run = skill_service.load_handler(_sk.skill_id, _sk.version)
                    context = {"task": task, "now": datetime.now()}
                    result = run(task, context)
                    handler_result = str(result) if result is not None else ""
                except Exception as e:  # noqa: BLE001 — handler 失败不炸对话，告知子 Agent
                    logger.warning("技能 %s handler 执行失败: %s", _sk.name, e)
                    handler_result = f"（handler 执行失败: {e}）"

            prompt = _sk.body
            user_content = task
            if handler_result:
                prompt = (
                    f"{_sk.body}\n\n---\n"
                    f"【系统执行结果（handler 已运行，以下为真实数据）】\n{handler_result}\n"
                    f"请基于以上真实数据回答用户任务，不要声称无法获取。"
                )
                user_content = f"{task}\n\n（系统已通过 handler 获取真实数据，见系统提示中的执行结果）"

            sub_agent = create_react_agent(model=_llm, tools=[], prompt=prompt)
            text: list[str] = []
            async for ev in sub_agent.astream_events(
                {"messages": [HumanMessage(content=user_content)]}, version="v2"
            ):
                if ev.get("event") == "on_chat_model_stream":
                    chunk = ev["data"]["chunk"]
                    t = chunk.text() if hasattr(chunk, "text") else str(chunk.content)
                    if t:
                        text.append(t)
            return "".join(text) or "（技能无输出）"

        tools.append(
            StructuredTool.from_function(
                coroutine=_run,
                name=sk.name,
                description=f"{sk.description}\n\n当用户任务匹配该技能时调用。",
                args_schema=_SkillArgs,
            )
        )
    return tools
