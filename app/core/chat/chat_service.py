"""对话内核：一次对话回合 → 抽象事件流。

run_chat_turn 只产出 Pydantic 事件，不关心协议编码；调用方（SSE / 未来飞书）负责序列化。
"""
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
    UsageEvent,
)


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

            # 3. ReAct Agent：注入绑定技能为工具；prompt 取 Agent 配置或全局默认
            prompt = agent_ctx.system_prompt if agent_ctx else settings.agent_system_prompt
            tools = build_skill_tools(agent_ctx, llm) if agent_ctx else []
            agent = create_react_agent(model=llm, tools=tools, prompt=prompt)
            # 绑定技能读盘失败被跳过时，在回复前明确提示用户
            if agent_ctx and getattr(agent_ctx, "skipped_skills", None):
                names = ", ".join(agent_ctx.skipped_skills)
                yield DeltaEvent(content=f"（提示：绑定技能 {names} 的文件读取失败，本轮未注入为工具）\n\n")

            # 4. 流式消费：on_chat_model_stream 捕获 token，on_chat_model_end 捕获 usage
            prompt_tokens = completion_tokens = 0
            delta_count = 0
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
                    if um:
                        prompt_tokens = um.get("input_tokens", 0)
                        completion_tokens = um.get("output_tokens", 0)
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
