"""对话运行时装配：按会话的 Agent 解析 LLM 与技能工具。

DB 解析在请求作用域完成；事件流阶段只使用纯内存对象（与 chat_service 的既有模式一致）。
"""
import logging
import re
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

# 工具名约束（与技能名一致：LangChain/OpenAI function-calling 可用名）
_TOOL_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


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
class KbInfo:
    kb_id: str
    name: str
    description: str
    tool_name: str  # KB 名合法则用之，否则 kb_{kb_id[:8]}
    emb: LlmSpec | None = None  # 检索用的 embedding 配置


@dataclass
class AgentChatContext:
    agent_id: str
    system_prompt: str
    llm: LlmSpec | None = None
    skills: list[SkillInfo] = field(default_factory=list)
    skipped_skills: list[str] = field(default_factory=list)  # 读盘失败被跳过的技能名
    kbs: list[KbInfo] = field(default_factory=list)
    skipped_kbs: list[str] = field(default_factory=list)  # embedding 配置缺失被跳过的知识库名


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

    # Kbs：绑定的知识库 → 解析各自 embedding 配置；缺失/停用进 skipped_kbs，不炸对话
    from app.core.kb import kb_service
    from app.models import KnowledgeBase

    for kid in await agent_service.get_bound_kb_ids(db, agent.agent_id):
        kb = (
            await db.execute(select(KnowledgeBase).where(KnowledgeBase.kb_id == kid))
        ).scalar_one_or_none()
        if kb is None:
            continue
        try:
            emb = await kb_service.get_embedding_spec(db, kb)
        except Exception:  # noqa: BLE001 — 解析异常按配置缺失处理
            logger.warning("知识库 %s embedding 配置解析失败", kid, exc_info=True)
            emb = None
        if emb is None:
            logger.warning("知识库 %s（%s）无可用的 embedding 配置，跳过挂载", kb.name, kid)
            ctx.skipped_kbs.append(kb.name)
            continue
        tool_name = kb.name if _TOOL_NAME_RE.match(kb.name) else f"kb_{kb.kb_id[:8]}"
        ctx.kbs.append(KbInfo(
            kb_id=kb.kb_id, name=kb.name, description=kb.description,
            tool_name=tool_name, emb=emb,
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


class _KbQueryArgs(BaseModel):
    query: str = Field(description="要检索的问题或关键词")


def build_kb_tools(ctx: AgentChatContext) -> list[StructuredTool]:
    """每个挂载的知识库 = 一个检索工具（余弦 top-k，结果带文档来源）。"""
    from app.core.kb import kb_service

    tools = []
    for kb in ctx.kbs:
        async def _run(query: str, _kb=kb) -> str:
            from app.db import get_engine

            # 事件流阶段不持有请求 session，检索用短生命周期会话
            from sqlalchemy.ext.asyncio import async_sessionmaker

            try:
                async with async_sessionmaker(get_engine(), expire_on_commit=False)() as db:
                    results = await kb_service.search_kb(db, _kb.kb_id, query)
            except Exception as e:  # noqa: BLE001 — 检索失败不炸对话
                logger.warning("知识库 %s 检索失败: %s", _kb.name, e)
                return f"（知识库检索失败: {e}）"
            if not results:
                return "（知识库中未找到相关内容）"
            parts = []
            for r in results:
                parts.append(f"[{_kb.name} · 块#{r['seq']} · 相关度{r['score']}]\n{r['content']}")
            return "\n\n".join(parts)

        tools.append(
            StructuredTool.from_function(
                coroutine=_run,
                name=kb.tool_name,
                description=(
                    f"知识库检索：{kb.description or kb.name}\n"
                    f"当用户问题可能需要该知识库中的资料时调用，入参为检索问题或关键词。"
                ),
                args_schema=_KbQueryArgs,
            )
        )
    return tools
