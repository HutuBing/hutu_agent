"""SKILL.md 解析与安全校验（纯函数，无 IO）。"""
import re

import yaml
from pydantic import BaseModel


class SkillParseError(Exception):
    """SKILL.md 格式或校验失败。"""


# 工具名约束：LangChain/OpenAI function-calling 可用名
_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
# Windows 盘符
_DRIVE_RE = re.compile(r"^[A-Za-z]:")


class SkillMeta(BaseModel):
    name: str
    description: str
    tags: list[str] = []
    files: list[str] = []
    body: str = ""


def parse_skill_md(raw: bytes | str) -> SkillMeta:
    """解析 SKILL.md：--- frontmatter（YAML）+ Markdown 正文。"""
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    if not text.startswith("---"):
        raise SkillParseError("SKILL.md 必须以 --- frontmatter 开头")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise SkillParseError("SKILL.md frontmatter 未正确闭合（缺少第二个 ---）")
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as e:
        raise SkillParseError(f"frontmatter YAML 解析失败: {e}") from e
    if not isinstance(meta, dict):
        raise SkillParseError("frontmatter 必须是键值对")

    name = str(meta.get("name", "")).strip()
    description = str(meta.get("description", "")).strip()
    if not name:
        raise SkillParseError("frontmatter 缺少必填字段: name")
    if not description:
        raise SkillParseError("frontmatter 缺少必填字段: description")

    validate_name(name)
    tags = [str(t).strip() for t in (meta.get("tags") or []) if str(t).strip()]
    files = meta.get("files") or []
    if not isinstance(files, list):
        raise SkillParseError("files 必须是列表")
    files = [str(f).strip() for f in files if str(f).strip()]
    validate_files(files)

    return SkillMeta(name=name, description=description, tags=tags, files=files, body=parts[2].strip())


def validate_name(name: str) -> None:
    if not _NAME_RE.match(name):
        raise SkillParseError(
            f"技能名 {name!r} 不合法：仅允许字母/数字/下划线/连字符，长度 1-64"
        )


def validate_files(files: list[str]) -> None:
    """防路径遍历：禁 ..、绝对路径、盘符、空字节。"""
    for f in files:
        if not f or "\0" in f:
            raise SkillParseError(f"非法文件路径: {f!r}")
        if ".." in f.split("/") + f.split("\\"):
            raise SkillParseError(f"文件路径不允许 ..: {f!r}")
        if f.startswith("/") or f.startswith("\\"):
            raise SkillParseError(f"文件路径不允许绝对路径: {f!r}")
        if _DRIVE_RE.match(f):
            raise SkillParseError(f"文件路径不允许盘符: {f!r}")
