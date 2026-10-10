"""对话内核：一次对话回合 → 抽象事件流。

run_chat_turn 只产出 Pydantic 事件，不关心协议编码；调用方（SSE / 未来飞书）负责序列化。
"""
import json
import time
import uuid
from collections.abc import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.prebuilt import create_react_agent

from app.config import get_settings
from app.core.chat.sse_events import (
    CancelledEvent,
    DeltaEvent,
    ErrorEvent,
    MsgEndEvent,
    MsgStartEvent,
    SSEEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
    UsageEvent,
)

ARGS_MAX = 2000  # 工具入参截断上限
OUTPUT_MAX = 500  # 工具输出预览截断上限


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def _build_fake_stream(text: str) -> AsyncIterator[str]:
    """演示模式：把固定回复逐字吐出，模拟 LLM token 流。"""

    async def gen() -> AsyncIterator[str]:
        for ch in text:
            yield ch

    return gen()


async def run_chat_turn(
    user_input: str,
    history: list[dict],
    request_disconnected=None,
    agent_ctx=None,
) -> AsyncIterator[SSEEvent]:
    """跑一轮对话，产出 SSE v3 抽象事件流。

    history: [{"role": "user"|"assistant", "content": str}, ...]，不含本轮输入。
    request_disconnected: 可选 awaitable 工厂，每个事件循环检查一次客户端断连。
    agent_ctx: AgentChatContext | None；None = 全局默认（LLM 走 .env、无技能工具）。
    """
    settings = get_settings()
    message_id = uuid.uuid4().hex
    yield MsgStartEvent(message_id=message_id)

    try:
        # 1. 构建 LLM 与工具：fake 优先；绑定配置 → 全局回退
        if settings.llm_fake:
            reply_text = f"（演示模式）收到：{user_input}"
            async for token in _build_fake_stream(reply_text):
                if request_disconnected is not None and await request_disconnected():
                    yield CancelledEvent()
                    yield MsgEndEvent()
                    return
                yield DeltaEvent(content=token)
            usage = (0, len(reply_text), len(reply_text))
        else:
            from app.core.agent.runtime import build_chat_model, build_skill_tools

            llm = build_chat_model(agent_ctx.llm if agent_ctx else None)

            # 2. 组装消息：历史 + 本轮输入
            messages = []
            for m in history:
                if m["role"] == "user":
                    messages.append(HumanMessage(content=m["content"]))
                elif m["role"] == "assistant":
                    messages.append(AIMessage(content=m["content"]))
            messages.append(HumanMessage(content=user_input))

            # 3. ReAct Agent：注入绑定技能与知识库工具；prompt 取 Agent 配置或全局默认
            prompt = agent_ctx.system_prompt if agent_ctx else settings.agent_system_prompt
            tools = []
            if agent_ctx:
                from app.core.agent.runtime import build_kb_tools, build_skill_tools

                tools = build_skill_tools(agent_ctx, llm) + build_kb_tools(agent_ctx)
            agent = create_react_agent(model=llm, tools=tools, prompt=prompt)
            # 绑定的技能/知识库装配失败被跳过时，在回复前明确提示用户
            skipped_notes = []
            if agent_ctx and getattr(agent_ctx, "skipped_skills", None):
                skipped_notes.append(f"绑定技能 {', '.join(agent_ctx.skipped_skills)} 的文件读取失败")
            if agent_ctx and getattr(agent_ctx, "skipped_kbs", None):
                skipped_notes.append(
                    f"挂载知识库 {', '.join(agent_ctx.skipped_kbs)} 缺少可用的 embedding 配置"
                )
            if skipped_notes:
                yield DeltaEvent(content=f"（提示：{'；'.join(skipped_notes)}，本轮未生效）\n\n")

            # 4. 流式消费：模型 token / 工具调用 / usage 统一转成抽象事件
            prompt_tokens = completion_tokens = 0
            delta_count = 0
            tool_started_at: dict[str, float] = {}  # run_id -> monotonic 起点
            try:
                async for ev in agent.astream_events(
                    {"messages": messages},
                    version="v2",
                    config={"recursion_limit": settings.agent_recursion_limit},
                ):
                    if request_disconnected is not None and await request_disconnected():
                        yield CancelledEvent()
                        yield MsgEndEvent()
                        return
                    kind = ev.get("event")
                    if kind == "on_chat_model_stream":
                        chunk = ev["data"]["chunk"]
                        text = chunk.text() if hasattr(chunk, "text") else str(chunk.content)
                        if text:
                            delta_count += 1
                            yield DeltaEvent(content=text)
                    elif kind == "on_chat_model_end":
                        out = ev["data"].get("output")
                        um = getattr(out, "usage_metadata", None)
                        if um:  # ReAct 多轮模型调用，累加而非覆盖
                            prompt_tokens += um.get("input_tokens", 0)
                            completion_tokens += um.get("output_tokens", 0)
                    elif kind == "on_tool_start":
                        run_id = ev.get("run_id", "")
                        tool_started_at[run_id] = time.monotonic()
                        yield ToolCallStartEvent(
                            run_id=run_id,
                            name=ev.get("name", ""),
                            args_json=_clip(
                                json.dumps(ev["data"].get("input", {}), ensure_ascii=False),
                                ARGS_MAX,
                            ),
                        )
                    elif kind == "on_tool_end":
                        run_id = ev.get("run_id", "")
                        started = tool_started_at.pop(run_id, None)
                        out = ev["data"].get("output")
                        text = out.content if hasattr(out, "content") else str(out)
                        yield ToolCallEndEvent(
                            run_id=run_id,
                            name=ev.get("name", ""),
                            duration_ms=int((time.monotonic() - started) * 1000) if started else 0,
                            output_preview=_clip(text, OUTPUT_MAX),
                        )
                    elif kind == "on_tool_error":
                        run_id = ev.get("run_id", "")
                        tool_started_at.pop(run_id, None)
                        yield ToolCallEndEvent(
                            run_id=run_id,
                            name=ev.get("name", ""),
                            duration_ms=0,
                            output_preview=_clip(str(ev["data"].get("error", "")), OUTPUT_MAX),
                            status="error",
                        )
            finally:
                tool_started_at.clear()  # 取消/异常时防泄漏
            # 网关流式偶发只发 reasoning 不发 content（glm 推理模型），全空时兜底提示而非静默
            if delta_count == 0:
                yield ErrorEvent(
                    code="empty_response",
                    message="模型未返回内容（网关流式响应异常），请重试",
                )
            usage = (prompt_tokens, completion_tokens, prompt_tokens + completion_tokens)

        yield UsageEvent(
            prompt_tokens=usage[0],
            completion_tokens=usage[1],
            total_tokens=usage[2],
        )
    except Exception as e:  # noqa: BLE001 — 兜底：任何异常都以 error + msg_end 收尾
        yield ErrorEvent(message=str(e))
    yield MsgEndEvent()
