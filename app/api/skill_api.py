"""技能管理 API。"""
import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import UserInfo, get_dev_user
from app.core.skill import skill_service
from app.core.skill.skill_parser import SkillParseError
from app.db import get_db

router = APIRouter(tags=["skills"])


@router.post("/api/skills", status_code=201)
async def upload_skill(
    files: list[UploadFile],
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(get_dev_user),
):
    contents = {}
    for f in files:
        contents[f.filename or ""] = await f.read()
    try:
        skill = await skill_service.upload_skill(db, contents, user.user_id)
    except SkillParseError as e:
        raise HTTPException(400, str(e))
    except skill_service.SkillServiceError as e:
        raise HTTPException(400, str(e))
    return skill_service.to_dict(skill)


@router.get("/api/skills")
async def list_skills(
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(get_dev_user),
):
    return [skill_service.to_dict(s) for s in await skill_service.list_skills(db)]


@router.get("/api/skills/{skill_id}")
async def get_skill(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(get_dev_user),
):
    s = await skill_service.get_skill(db, skill_id)
    if s is None:
        raise HTTPException(404, "skill not found")
    detail = skill_service.to_dict(s)
    detail["versions"] = [
        {"version": v.version, "files": json.loads(v.files_json)}
        for v in await skill_service.list_versions(db, skill_id)
    ]
    return detail


@router.get("/api/skills/{skill_id}/versions/{version}")
async def get_version_content(
    skill_id: str,
    version: int,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(get_dev_user),
):
    try:
        return await skill_service.get_version_content(db, skill_id, version)
    except skill_service.SkillServiceError as e:
        raise HTTPException(404, str(e))


@router.delete("/api/skills/{skill_id}")
async def delete_skill(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(get_dev_user),
):
    s = await skill_service.get_skill(db, skill_id)
    if s is None:
        raise HTTPException(404, "skill not found")
    await skill_service.delete_skill(db, s)
    return {"ok": True}
