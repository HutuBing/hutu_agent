"""skill_parser 测试：合法解析 + 各类非法输入。"""
import pytest

from app.core.skill.skill_parser import SkillParseError, parse_skill_md, validate_files

VALID = """---
name: oss_uploader
description: "OSS 文件上传技能"
tags: [oss, upload]
files:
  - examples/upload.py
  - templates/policy.json
---
你是 OSS 上传专家。
"""


def test_valid():
    meta = parse_skill_md(VALID)
    assert meta.name == "oss_uploader"
    assert meta.description == "OSS 文件上传技能"
    assert meta.tags == ["oss", "upload"]
    assert meta.files == ["examples/upload.py", "templates/policy.json"]
    assert "OSS 上传专家" in meta.body


@pytest.mark.parametrize("raw", [
    "",  # 非 --- 开头
    "---\nname: x\n",  # frontmatter 未闭合
    "---\nnot: [valid\n---\nbody",  # YAML 非法
    "---\ndescription: d\n---\nbody",  # 缺 name
    "---\nname: x\n---\nbody",  # 缺 description
    "---\nname: 无效名称!\ndescription: d\n---\nbody",  # name 不合法
])
def test_invalid(raw):
    with pytest.raises(SkillParseError):
        parse_skill_md(raw)


@pytest.mark.parametrize("f", [
    "../x.py",       # 路径遍历
    "a/../../b.py",  # 间接遍历
    "/abs/x.py",     # 绝对路径
    "C:\\x\\y.py",   # 盘符
    "a\x00b.py",     # 空字节
])
def test_path_traversal(f):
    with pytest.raises(SkillParseError):
        validate_files([f])


def test_files_ok():
    validate_files(["a.py", "dir/b.json", "deep/dir/c.md"])
