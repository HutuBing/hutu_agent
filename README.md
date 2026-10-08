# hutu_agent

云端 Agent 平台 MVP：多轮流式对话（SSE v3），基于 FastAPI + LangGraph ReAct。

## MVP 范围

- ✅ 会话管理（创建 / 列表 / 历史）
- ✅ SSE v3 流式对话（`msg_start / delta / usage / cancelled / error / msg_end`）
- ✅ 消息落库，多轮上下文
- ✅ 客户端断连中断（cancelled 事件）
- ✅ 无 Key 演示模式（`HUTU_LLM_FAKE=1`，逐字回显，不调真实 LLM）
- ❌ 暂不包含：SSO 登录（dev 固定用户）、沙箱、LLM 配置管理、Skills/OSS、可观测

## 快速开始

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt   # Windows
# cp .env.example .env 并按需填写；无 Key 时设 HUTU_LLM_FAKE=1

.venv/Scripts/python -m uvicorn app.main:app --reload --port 8900
```

启动后浏览器打开 **http://127.0.0.1:8900/** 即是聊天界面：左侧新建/切换会话，输入消息流式回答，显示 token 用量，可点"停止"中断。

## API

| 方法 | 路径 | 说明 |
|-|-|-|
| POST | `/api/sessions` | 创建会话 `{agent_id?, title?}` |
| GET | `/api/sessions` | 当前用户会话列表 |
| GET | `/api/sessions/{id}/messages` | 历史消息 |
| POST | `/api/sessions/{id}/chat` | 对话（SSE 流，`data: {json}\n\n`） |
| GET | `/health` | 健康检查 |

对话请求示例：

```bash
curl -N -X POST http://127.0.0.1:8900/api/sessions/<sid>/chat \
  -H "Content-Type: application/json" -d '{"content":"你好"}'
```

## 配置（环境变量，前缀 `HUTU_`）

| 变量 | 说明 |
|-|-|
| `HUTU_DB_URL` | 默认 SQLite；生产可切 `mysql+aiomysql://...` |
| `HUTU_LLM_BASE_URL` / `HUTU_LLM_API_KEY` / `HUTU_LLM_MODEL` | OpenAI 兼容协议 |
| `HUTU_LLM_FAKE` | 置 1 为演示模式，逐字回显 |
| `HUTU_AGENT_SYSTEM_PROMPT` | 默认 Agent system prompt |
| `HUTU_DEV_USER_ID` / `HUTU_DEV_USER_NAME` | dev 固定用户（替代 SSO） |

## 测试

```bash
.venv/Scripts/python -m pytest tests/ -q
```

## 后续路线

按概设文档推进：SSO 三鉴权 → LLM 配置管理（Fernet 加密 + 配额）→ 内置工具池 → 沙箱 → Skills/OSS → 可观测（OTel+ARMS）。
