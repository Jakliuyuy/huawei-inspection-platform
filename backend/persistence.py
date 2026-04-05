from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable


type DbConnect = Callable[[], sqlite3.Connection]
type NowLocal = Callable[[], datetime]


def cleanup_expired_data(
    *,
    db_connect: DbConnect,
    now_local: NowLocal,
    retention_days: int,
) -> None:
    cutoff = now_local() - timedelta(days=retention_days)
    conn = db_connect()
    with conn:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now_local().isoformat(),))
        jobs = conn.execute(
            "SELECT id, input_path, output_path, bundle_path, finished_at FROM jobs WHERE finished_at IS NOT NULL"
        ).fetchall()
        for job in jobs:
            finished_at = datetime.fromisoformat(job["finished_at"])
            if finished_at >= cutoff:
                continue
            for field in ("input_path", "output_path", "bundle_path"):
                value = job[field]
                if not value:
                    continue
                path = Path(value)
                if path.is_file():
                    path.unlink(missing_ok=True)
                elif path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
            conn.execute("DELETE FROM jobs WHERE id = ?", (job["id"],))
        conn.execute("DELETE FROM audit_logs WHERE created_at < ?", (cutoff.isoformat(),))
    conn.close()


def recover_incomplete_jobs(*, db_connect: DbConnect, now_local: NowLocal) -> None:
    conn = db_connect()
    with conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = 'failed',
                progress = CASE WHEN progress >= 100 THEN progress ELSE 100 END,
                status_detail = '服务重启，任务已中断',
                finished_at = COALESCE(finished_at, ?),
                error_message = COALESCE(error_message, '服务重启前任务未完成，请重新提交')
            WHERE status IN ('queued', 'running')
            """,
            (now_local().isoformat(),),
        )
    conn.close()


def summarize_job_stats(conn: sqlite3.Connection, user: sqlite3.Row) -> dict[str, int]:
    if user["is_admin"]:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status IN ('queued', 'running') THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed
            FROM jobs
            """
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status IN ('queued', 'running') THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed
            FROM jobs
            WHERE user_id = ?
            """,
            (user["id"],),
        ).fetchone()
    return {
        "total": row["total"] or 0,
        "active": row["active"] or 0,
        "completed": row["completed"] or 0,
        "failed": row["failed"] or 0,
    }


def list_jobs_page(
    *,
    db_connect: DbConnect,
    user: sqlite3.Row,
    page: int,
    page_size: int,
) -> tuple[list[sqlite3.Row], int, dict[str, int]]:
    offset = (page - 1) * page_size
    conn = db_connect()
    stats = summarize_job_stats(conn, user)
    if user["is_admin"]:
        rows = conn.execute(
            """
            SELECT jobs.*, users.username
            FROM jobs JOIN users ON users.id = jobs.user_id
            ORDER BY jobs.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (page_size, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT jobs.*, users.username
            FROM jobs JOIN users ON users.id = jobs.user_id
            WHERE jobs.user_id = ?
            ORDER BY jobs.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (user["id"], page_size, offset),
        ).fetchall()
    conn.close()
    return rows, stats["total"], stats


def list_admin_users(*, db_connect: DbConnect) -> list[sqlite3.Row]:
    conn = db_connect()
    rows = conn.execute("SELECT id, username, is_admin, created_at, last_login_at FROM users ORDER BY created_at").fetchall()
    conn.close()
    return rows


def list_audits_page(*, db_connect: DbConnect, page: int, page_size: int) -> tuple[list[sqlite3.Row], int]:
    offset = (page - 1) * page_size
    conn = db_connect()
    audits = conn.execute(
        """
        SELECT audit_logs.*, users.username
        FROM audit_logs LEFT JOIN users ON users.id = audit_logs.user_id
        ORDER BY audit_logs.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (page_size, offset),
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
    conn.close()
    return audits, total
