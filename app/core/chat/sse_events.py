"""SSE v3 事件模型（MVP 子集：msg_start / delta / usage / error / cancelled / msg_end）。

与概设《Chat_SSE_前端接口文档》对齐；后续扩展 intent/suggestions/references/action/tool_call_* 等。
"""
from typing import Literal

from pydantic import BaseModel


class MsgStartEvent(BaseModel):
    type: Literal["msg_start"] = "msg_start"
    message_id: str


class DeltaEvent(BaseModel):
    type: Literal["delta"] = "delta"
    content: str


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
    MsgStartEvent | DeltaEvent | UsageEvent | CancelledEvent | ErrorEvent | MsgEndEvent
)
