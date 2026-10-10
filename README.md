# hutu_agent

云端 Agent 平台：多轮流式对话（SSE v3）+ Skill / LLM 配置 / Agent 管理，基于 FastAPI + LangGraph ReAct。

## 功能总览

| 模块 | 能力 |
|---|---|
| 对话 | 多轮流式对话（`msg_start/delta/usage/cancelled/error/msg_end`）、历史落库、前端中断 |
| Agent 管理 | 创建/编辑/删除 Agent，绑定技能（多选）、知识库（多选）与大模型（单选），对话时动态装配 |
| Skill 管理 | SKILL.md 上传（YAML frontmatter 校验 + 路径安全）、本地磁盘版本化存储、同名自动升版本 |
| 知识库 | 上传 .md/.txt/.pdf → 切块 → embedding 向量化（余弦 top-5 检索）；Agent 挂载后对话中自动出检索工具卡片 |
| LLM 配置 | 多供应商配置（用途：对话 / 向量嵌入），API Key Fernet 加密落库、列表脱敏（`sk-****abcd`）、留空即不改 |
| 选择优先级 | 会话 Agent 绑定的 LLM → `.env` 全局回退；技能未绑定时不注入工具 |

## 快速开始

```bash
# 后端
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt   # Windows
# cp .env.example .env 并填写；必配：
#   HUTU_LLM_ENCRYPTION_KEY（python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"）
#   HUTU_LLM_* 三项（真实模型）；无 Key 演示设 HUTU_LLM_FAKE=1

# 前端（Vue 3 + Vite，首次需 Node 20+）
cd web
npm install          # 内网环境先 npm config set registry https://registry.npmmirror.com
npm run build        # 产物 dist/ 由 FastAPI 托管；开发模式用 npm run dev（5173 代理到 8900）

# 启动
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8900   # 项目根目录执行
```

浏览器打开 **http://127.0.0.1:8900/**（hash 路由 `/#/chat`）—— 对话 / Agent 管理 / Skill 管理 / LLM 配置。

**推荐体验路径**：LLM 配置页建配置 → Skill 管理页上传 SKILL.md（可附 handler.py 提供真实数据源）→ Agent 管理页建 Agent 并绑定两者 → 对话页新建会话选该 Agent → 提问即可看到**工具调用卡片**（转圈 → 耗时 → 可展开输入/输出），历史消息同样回显。

### SKILL.md + handler 格式

```markdown
---
name: my_skill          # 工具名，^[a-zA-Z0-9_-]{1,64}$，全库唯一
description: "技能描述（作为工具 description 供模型判断何时调用）"
tags: [tag1, tag2]
files:                  # 可选附属文件，随正文一起存储
  - examples/demo.py
---
技能正文（作为执行该技能的子 Agent 的 system_prompt）
```

可选 `handler.py`（与 SKILL.md 一起上传）：提供 `run(task, context) -> str`，工具执行时**先在主进程运行它获取真实数据**（context 含 `task`、`now`），再把数据注入子 Agent 生成回复。示例见 time_teller 技能。

技能文件存储在 `{HUTU_SKILL_DATA_DIR}/skills/{skill_id}/v{version}/`（与概设 OSS 路径规则一致，后续切 OSS 只改 skill_service 落盘/读盘两处）。

## API

| 方法 | 路径 | 说明 |
|-|-|-|
| POST/GET | `/api/sessions` | 创建（可选 `agent_id`）/ 列表 |
| GET | `/api/sessions/{id}/messages` | 历史消息 |
| POST | `/api/sessions/{id}/chat` | 对话（SSE 流，`data: {json}\n\n`） |
| POST/GET/DELETE | `/api/skills` (+`/{id}`, `/{id}/versions/{v}`) | 技能上传(multipart)/列表/详情/版本查看/删除 |
| GET/POST/PUT/DELETE | `/api/kbs` (+`/{id}`, `/{id}/documents[/{doc_id}]`) | 知识库 CRUD / 文档上传(multipart，自动切块向量化)/文档删除 |
| GET/POST/PUT/DELETE | `/api/llm-configs` (+`/{id}`) | LLM 配置 CRUD（key 仅脱敏返回；`usage`=chat/embedding） |
| GET/POST/PUT/DELETE | `/api/agents` (+`/{id}`) | Agent CRUD（含 skill_ids[] + kb_ids[] + config_id 绑定） |
| GET | `/health` | 健康检查（含 llm_fake 标志） |

## 配置（环境变量，前缀 `HUTU_`）

| 变量 | 说明 |
|-|-|
| `HUTU_DB_URL` | 默认 SQLite；生产可切 `mysql+aiomysql://...` |
| `HUTU_LLM_BASE_URL` / `HUTU_LLM_API_KEY` / `HUTU_LLM_MODEL` | 全局回退 LLM（OpenAI 兼容协议） |
| `HUTU_LLM_FAKE` | 置 1 为演示模式（逐字回显，技能工具不生效） |
| `HUTU_LLM_ENCRYPTION_KEY` | Fernet 密钥，LLM 配置加解密用 |
| `HUTU_SKILL_DATA_DIR` | 技能文件目录，默认 `./data` |
| `HUTU_AGENT_RECURSION_LIMIT` | Agent 工具调用轮数上限，默认 25 |
| `HUTU_AGENT_SYSTEM_PROMPT` | 默认 system prompt |
| `HUTU_DEV_USER_ID` / `HUTU_DEV_USER_NAME` | dev 固定用户（替代 SSO） |

## 测试

```bash
.venv/Scripts/python -m pytest tests/ -q    # 33 个测试
```

## 知识库（RAG）说明

- 先到 **LLM 配置页** 新建一条 `用途=向量嵌入` 的配置（OpenAI 兼容 embeddings 端点，如 dashscope 的 `text-embedding-v3`）
- **知识库页** 建库时绑定该配置 → 上传 .md/.txt/.pdf（单文件 2MB），自动切块（~600 字/块，带重叠）并向量化存 SQLite
- **Agent 管理页** 挂载知识库后，对话中每个知识库是一个检索工具（工具名=库名，非法字符自动 `kb_xxxxxxxx`），检索 top-5 片段，命中过程在工具卡片中可见
- Agent 挂载的知识库若缺 embedding 配置，对话开头会提示「挂载知识库 … 本轮未生效」，不中断对话

## 后续路线（按概设）

SSO 三鉴权 → 配额/用量统计 → 内置工具池（http/sandbox 执行器）→ e2b 沙箱 → Skill OSS+pub-sub 同步 → 可观测（OTel+ARMS）。
