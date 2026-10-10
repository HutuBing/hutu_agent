"""数据模型：会话、消息与 Agent/Skill/LLM 配置管理。"""
from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Session(Base):
    __tablename__ = "session"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    agent_id: Mapped[str] = mapped_column(String(36), default="default")
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Message(Base):
    __tablename__ = "message"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user / assistant
    content: Mapped[str] = mapped_column(Text)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MessageToolCall(Base):
    """assistant 消息期间的工具调用记录（支持历史回看工具卡片）。"""

    __tablename__ = "message_tool_call"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(36), index=True)  # 所属 assistant 消息
    session_id: Mapped[str] = mapped_column(String(36), index=True)  # 冗余，免 join
    tool_name: Mapped[str] = mapped_column(String(128))
    args_json: Mapped[str] = mapped_column(Text, default="")  # 完整入参 JSON（≤2000）
    output_preview: Mapped[str] = mapped_column(Text, default="")  # ≤500
    status: Mapped[str] = mapped_column(String(16), default="ok")  # ok / error
    duration_ms: Mapped[int] = mapped_column(default=0)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Agent(Base):
    __tablename__ = "agent"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(500), default="")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    multi_agent_enabled: Mapped[bool] = mapped_column(default=False)  # 预留，本期不生效
    creator_user_id: Mapped[str] = mapped_column(String(255), default="")
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    update_time: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Skill(Base):
    __tablename__ = "skill"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    skill_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)  # 即 LangChain tool name
    description: Mapped[str] = mapped_column(String(500), default="")  # 冗余自最新版
    tags: Mapped[str] = mapped_column(String(255), default="")  # 逗号分隔，冗余自最新版
    latest_version: Mapped[int] = mapped_column(default=1)
    creator_user_id: Mapped[str] = mapped_column(String(255), default="")
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    update_time: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class SkillVersion(Base):
    __tablename__ = "skill_version"
    __table_args__ = (UniqueConstraint("skill_id", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    skill_id: Mapped[str] = mapped_column(String(36), index=True)
    version: Mapped[int] = mapped_column(default=1)
    files_json: Mapped[str] = mapped_column(Text)  # 该版本落盘文件名 JSON 数组


class AgentSkillRel(Base):
    __tablename__ = "agent_skill_rel"
    __table_args__ = (UniqueConstraint("agent_id", "skill_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(36), index=True)
    skill_id: Mapped[str] = mapped_column(String(36), index=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class LlmConfig(Base):
    __tablename__ = "llm_config"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    provider: Mapped[str] = mapped_column(String(32), default="openai_compatible")
    api_base_url: Mapped[str] = mapped_column(String(255), default="")
    api_key_encrypted: Mapped[str] = mapped_column(Text, default="")  # Fernet 密文
    model_identifier: Mapped[str] = mapped_column(String(128), default="")
    usage: Mapped[str] = mapped_column(String(16), default="chat")  # chat / embedding
    price_per_1k_tokens: Mapped[float] = mapped_column(default=0.0)  # 本期仅存储展示
    quota_limit: Mapped[int] = mapped_column(default=0)  # 0=不限，本期仅存储
    status: Mapped[str] = mapped_column(String(16), default="enabled")  # enabled/disabled
    creator_user_id: Mapped[str] = mapped_column(String(255), default="")
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    update_time: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AgentLlmRel(Base):
    __tablename__ = "agent_llm_rel"
    __table_args__ = (UniqueConstraint("agent_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    config_id: Mapped[str] = mapped_column(String(36), index=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    kb_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(String(500), default="")
    embedding_config_id: Mapped[str] = mapped_column(String(36), default="")  # 绑定的向量化配置
    creator_user_id: Mapped[str] = mapped_column(String(255), default="")
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    update_time: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class KbDocument(Base):
    __tablename__ = "kb_document"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doc_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    kb_id: Mapped[str] = mapped_column(String(36), index=True)
    filename: Mapped[str] = mapped_column(String(255), default="")
    chunk_count: Mapped[int] = mapped_column(default=0)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KbChunk(Base):
    """知识库切块与向量（向量以 JSON 浮点数组存储，演示规模纯 Python 余弦检索）。"""

    __tablename__ = "kb_chunk"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    kb_id: Mapped[str] = mapped_column(String(36), index=True)
    doc_id: Mapped[str] = mapped_column(String(36), index=True)
    seq: Mapped[int] = mapped_column(default=0)  # 块在文档内的序号
    content: Mapped[str] = mapped_column(Text)
    vector_json: Mapped[str] = mapped_column(Text, default="")  # JSON float 数组


class AgentKbRel(Base):
    """Agent 挂载知识库的绑定关系。"""

    __tablename__ = "agent_kb_rel"
    __table_args__ = (UniqueConstraint("agent_id", "kb_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(36), index=True)
    kb_id: Mapped[str] = mapped_column(String(36), index=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
