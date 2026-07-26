"""报告文件路径解析。

两个解析器共用同一套防线：取 basename 归一化 → resolve → 校验仍在允许的
根目录内 → 限定 .docx 后缀。任务侧多一层 generated_files 白名单。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi import HTTPException

from backend.config import config


def job_report_names(job: sqlite3.Row) -> list[str]:
    generated_files = json.loads(job["generated_files"]) if job["generated_files"] else []
    return [Path(item).name for item in generated_files]


def resolve_job_report_path(job: sqlite3.Row, file_name: str) -> Path:
    safe_name = Path(str(file_name).replace("\\", "/")).name
    if not safe_name or safe_name not in job_report_names(job):
        raise HTTPException(status_code=400, detail=f"文件 {file_name} 不属于该任务")
    output_dir = Path(job["output_path"]).resolve()
    path = (output_dir / safe_name).resolve()
    if output_dir not in path.parents:
        raise HTTPException(status_code=400, detail="非法文件路径")
    if path.suffix.lower() != ".docx":
        raise HTTPException(status_code=400, detail="仅允许发送 Word 报告")
    return path


def resolve_admin_report_path(job_id: str, file_name: str) -> Path:
    path = (config.report_dir / job_id / Path(file_name).name).resolve()
    if config.report_dir not in path.parents:
        raise HTTPException(status_code=400, detail="非法文件路径")
    if path.suffix.lower() != ".docx":
        raise HTTPException(status_code=400, detail="仅允许管理 Word 报告")
    return path
