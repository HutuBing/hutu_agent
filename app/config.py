"""全局配置（pydantic-settings，从 .env / 环境变量读取）。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HUTU_", env_file=".env", extra="ignore")

    # 数据库
    db_url: str = "sqlite+aiosqlite:///./hutu_agent.db"

    # LLM（OpenAI 兼容协议）
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_fake: bool = False  # 无 Key 演示模式：不调真实 LLM，逐字回显

    # 默认 Agent
    agent_system_prompt: str = "你是一个乐于助人的通用智能助手。"

    # dev 固定用户（MVP 无 SSO）
    dev_user_id: str = "dev-user"
    dev_user_name: str = "开发用户"


@lru_cache
def get_settings() -> Settings:
    return Settings()
