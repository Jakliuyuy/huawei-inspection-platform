"""数据库行 → API 响应的序列化。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from backend.config import API_PREFIX, STATUS_LABELS


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def clamp_progress(value: int | None) -> int:
    if value is None:
        return 0
    return max(0, min(100, int(value)))


def timeline_steps(job: sqlite3.Row) -> list[dict[str, Any]]:
    steps = [
        ("任务已创建", "已进入任务队列", bool(job["created_at"])),
        ("开始处理", "工作线程已接管任务", bool(job["started_at"])),
        ("日志识别", "识别日志根目录和上传结构", job["status"] in {"running", "completed", "failed"}),
        ("报告生成", job["status_detail"] or "等待生成报告", clamp_progress(job["progress"]) >= 10),
        ("结果打包", "生成压缩包供下载", clamp_progress(job["progress"]) >= 95 or bool(job["bundle_path"])),
        ("任务完成", "可以下载报告结果", job["status"] == "completed"),
    ]
    if job["status"] == "failed":
        steps[-1] = ("任务失败", job["error_message"] or "处理过程中发生错误", True)
    return [
        {
            "step": index,
            "title": title,
            "description": desc,
            "active": active,
        }
        for index, (title, desc, active) in enumerate(steps, 1)
    ]


def serialize_job(row: sqlite3.Row) -> dict[str, Any]:
    generated_files = json.loads(row["generated_files"]) if row["generated_files"] else []
    generated_entries = []
    for file_path in generated_files:
        path = Path(file_path)
        generated_entries.append(
            {
                "name": path.name,
                "download_url": f"{API_PREFIX}/jobs/{row['id']}/files/{path.name}",
            }
        )
    return {
        "id": row["id"],
        "status": row["status"],
        "status_label": status_label(row["status"]),
        "progress": clamp_progress(row["progress"]),
        "status_detail": row["status_detail"] or "",
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "username": row["username"],
        "log_root": row["log_root"],
        "error_message": row["error_message"],
        "bundle_available": bool(row["bundle_path"]),
        "bundle_download_url": f"{API_PREFIX}/jobs/{row['id']}/download" if row["bundle_path"] else None,
        "generated_files": generated_entries,
        "timeline": timeline_steps(row),
    }


def serialize_user(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "username": row["username"],
        "is_admin": bool(row["is_admin"]),
        "role_label": "管理员" if row["is_admin"] else "普通用户",
        "created_at": row["created_at"],
        "last_login_at": row["last_login_at"],
    }


def serialize_audit(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "username": row["username"] or "匿名",
        "action": row["action"],
        "detail": row["detail"],
        "ip_address": row["ip_address"],
    }
