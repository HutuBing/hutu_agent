"""技能管理：CRUD、版本管理、磁盘读写。

存储路径规则与概设 OSS 对齐：{skill_data_dir}/skills/{skill_id}/v{version}/{filename}
未来切 OSS 只需替换本文件的落盘/读盘两个函数。
"""
import json
import shutil
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.skill.skill_parser import SkillParseError, SkillMeta, parse_skill_md
from app.models import AgentSkillRel, Skill, SkillVersion

MAX_FILE_SIZE = 1 * 1024 * 1024  # 单文件 1MB


class SkillServiceError(Exception):
    """技能业务错误。"""


def _skill_dir(skill_id: str, version: int) -> Path:
    return Path(get_settings().skill_data_dir) / "skills" / skill_id / f"v{version}"


async def list_skills(db: AsyncSession) -> list[Skill]:
    result = await db.execute(select(Skill).order_by(Skill.update_time.desc()))
    return list(result.scalars())


async def get_skill(db: AsyncSession, skill_id: str) -> Skill | None:
    return (
        await db.execute(select(Skill).where(Skill.skill_id == skill_id))
    ).scalar_one_or_none()


async def list_versions(db: AsyncSession, skill_id: str) -> list[SkillVersion]:
    result = await db.execute(
        select(SkillVersion)
        .where(SkillVersion.skill_id == skill_id)
        .order_by(SkillVersion.version.desc())
    )
    return list(result.scalars())


async def upload_skill(db: AsyncSession, files: dict[str, bytes], user_id: str) -> Skill:
    """上传一组文件（必须含 SKILL.md）。同名技能 → 新版本。"""
    raw = files.get("SKILL.md")
    if raw is None:
        raise SkillParseError("上传文件中必须包含 SKILL.md")
    meta: SkillMeta = parse_skill_md(raw)  # 先校验，失败不落盘

    skill = (
        await db.execute(select(Skill).where(Skill.name == meta.name))
    ).scalar_one_or_none()
    if skill is None:
        skill = Skill(
            skill_id=uuid.uuid4().hex,
            name=meta.name,
            description=meta.description,
            tags=",".join(meta.tags),
            latest_version=1,
            creator_user_id=user_id,
        )
        db.add(skill)
        await db.flush()
        version = 1
    else:
        version = skill.latest_version + 1
        skill.description = meta.description
        skill.tags = ",".join(meta.tags)
        skill.latest_version = version

    file_names = [f for f in files if f != "SKILL.md"]
    # 校验通过后一次性落盘
    vdir = _skill_dir(skill.skill_id, version)
    vdir.mkdir(parents=True, exist_ok=True)
    try:
        (vdir / "SKILL.md").write_bytes(raw)
        for fname, content in files.items():
            if fname == "SKILL.md":
                continue
            _safe_write(vdir, fname, content)
    except SkillServiceError:
        shutil.rmtree(vdir, ignore_errors=True)
        raise

    db.add(
        SkillVersion(
            skill_id=skill.skill_id,
            version=version,
            files_json=json.dumps(["SKILL.md", *file_names]),
        )
    )
    await db.commit()
    await db.refresh(skill)  # 回填服务端生成的 update_time，避免 to_dict 触发隐式 IO
    return skill


def _safe_write(vdir: Path, fname: str, content: bytes) -> None:
    if len(content) > MAX_FILE_SIZE:
        raise SkillServiceError(f"文件超过 1MB 上限: {fname}")
    target = (vdir / fname).resolve()
    if not target.is_relative_to(vdir.resolve()):  # 双保险
        raise SkillServiceError(f"非法文件路径: {fname}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)


async def read_skill_body(skill_id: str, version: int) -> str:
    """读最新指定版本的 SKILL.md 正文（供技能工具 system_prompt 用）。"""
    p = _skill_dir(skill_id, version) / "SKILL.md"
    if not p.exists():
        raise SkillServiceError(f"技能文件丢失: {p}")
    meta = parse_skill_md(p.read_bytes())
    return meta.body


async def get_version_content(db: AsyncSession, skill_id: str, version: int) -> dict:
    sv = (
        await db.execute(
            select(SkillVersion).where(
                SkillVersion.skill_id == skill_id, SkillVersion.version == version
            )
        )
    ).scalar_one_or_none()
    if sv is None:
        raise SkillServiceError("版本不存在")
    p = _skill_dir(skill_id, version) / "SKILL.md"
    if not p.exists():
        raise SkillServiceError("技能文件丢失")
    meta = parse_skill_md(p.read_bytes())
    return {
        "skill_id": skill_id,
        "version": version,
        "name": meta.name,
        "description": meta.description,
        "tags": meta.tags,
        "files": json.loads(sv.files_json),
        "body": meta.body,
    }


async def delete_skill(db: AsyncSession, skill: Skill) -> None:
    # 级联：版本记录、绑定关系、磁盘目录
    for sv in await list_versions(db, skill.skill_id):
        await db.delete(sv)
    for rel in (
        await db.execute(select(AgentSkillRel).where(AgentSkillRel.skill_id == skill.skill_id))
    ).scalars():
        await db.delete(rel)
    await db.delete(skill)
    await db.commit()
    shutil.rmtree(
        Path(get_settings().skill_data_dir) / "skills" / skill.skill_id, ignore_errors=True
    )


def to_dict(s: Skill) -> dict:
    return {
        "skill_id": s.skill_id,
        "name": s.name,
        "description": s.description,
        "tags": [t for t in s.tags.split(",") if t],
        "latest_version": s.latest_version,
        "update_time": str(s.update_time),
    }
