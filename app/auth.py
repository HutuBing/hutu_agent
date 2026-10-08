"""dev 固定用户（MVP 无 SSO，后续接入翼虎 SSO 时替换为鉴权中间件）。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class UserInfo:
    user_id: str
    username: str


def get_dev_user() -> UserInfo:
    from app.config import get_settings

    s = get_settings()
    return UserInfo(user_id=s.dev_user_id, username=s.dev_user_name)
