"""任务/公告/报告索引的直接查询与访问控制。"""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import HTTPException

from backend.config import LOCAL_TZ, now_local
from backend.db import db_connect
from backend.persistence import list_jobs_page as list_jobs_page_impl
from backend.reports import list_report_date_stats as list_report_date_stats_impl
from backend.reports import list_report_files_for_user as list_report_files_for_user_impl
from backend.reports import list_report_user_stats as list_report_user_stats_impl
from backend.reports import rebuild_report_file_index as rebuild_report_file_index_impl


def announcement_text() -> str:
    conn = db_connect()
    row = conn.execute("SELECT content FROM announcements WHERE id = 1").fetchone()
    conn.close()
    return row["content"] if row else ""


def get_job(job_id: str) -> sqlite3.Row | None:
    conn = db_connect()
    row = conn.execute(
        "SELECT jobs.*, users.username FROM jobs JOIN users ON users.id = jobs.user_id WHERE jobs.id = ?",
        (job_id,),
    ).fetchone()
    conn.close()
    return row


def ensure_job_access(job: sqlite3.Row | None, user: sqlite3.Row) -> sqlite3.Row:
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not user["is_admin"] and job["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="无权访问该任务")
    return job


def generate_job_id(conn: sqlite3.Connection) -> str:
    date_prefix = now_local().strftime("%Y%m%d")
    row = conn.execute(
        """
        SELECT id FROM jobs
        WHERE id LIKE ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (f"{date_prefix}-%",),
    ).fetchone()
    if not row:
        return f"{date_prefix}-001"
    _, _, suffix = row["id"].partition("-")
    sequence = int(suffix) + 1 if suffix.isdigit() else 1
    return f"{date_prefix}-{sequence:03d}"


def list_jobs_page(user: sqlite3.Row, page: int, page_size: int) -> tuple[list[sqlite3.Row], int, dict[str, int]]:
    return list_jobs_page_impl(db_connect=db_connect, user=user, page=page, page_size=page_size)


def rebuild_report_file_index() -> None:
    rebuild_report_file_index_impl(db_connect=db_connect, local_tz=LOCAL_TZ)


def list_report_date_stats() -> list[dict[str, Any]]:
    return list_report_date_stats_impl(db_connect=db_connect)


def list_report_user_stats(report_date: str) -> list[dict[str, Any]]:
    return list_report_user_stats_impl(db_connect=db_connect, report_date=report_date)


def list_report_files_for_user(report_date: str, username: str) -> list[dict[str, str]]:
    return list_report_files_for_user_impl(db_connect=db_connect, report_date=report_date, username=username)
