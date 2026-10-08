"""SSE v3 事件模型（msg_start / delta / tool_call_* / usage / error / cancelled / msg_end）。

与概设《Chat_SSE_前端接口文档》对齐；后续扩展 intent/suggestions/references/action 等。
"""
from typing import Literal

from pydantic import BaseModel


class MsgStartEvent(BaseModel):
    type: Literal["msg_start"] = "msg_start"
    message_id: str


class DeltaEvent(BaseModel):
    type: Literal["delta"] = "delta"
    content: str


class ToolCallStartEvent(BaseModel):
    type: Literal["tool_call_start"] = "tool_call_start"
    run_id: str  # LangGraph run_id，前后端配对键（同轮可能多次调工具）
    name: str  # 技能名 = tool name
    args_json: str = ""  # 工具入参 JSON 字符串（服务端截断 2000）


class ToolCallEndEvent(BaseModel):
    type: Literal["tool_call_end"] = "tool_call_end"
    run_id: str
    name: str
    duration_ms: int = 0
    output_preview: str = ""  # 截断 500 字符
    status: str = "ok"  # ok / error


class UsageEvent(BaseModel):
    type: Literal["usage"] = "usage"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class CancelledEvent(BaseModel):
    type: Literal["cancelled"] = "cancelled"


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    code: str = "internal_error"
    message: str


class MsgEndEvent(BaseModel):
    type: Literal["msg_end"] = "msg_end"


SSEEvent = (
    MsgStartEvent
    | DeltaEvent
    | ToolCallStartEvent
    | ToolCallEndEvent
    | UsageEvent
    | CancelledEvent
    | ErrorEvent
    | MsgEndEvent
)
