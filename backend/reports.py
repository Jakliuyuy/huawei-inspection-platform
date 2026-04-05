from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


type DbConnect = Callable[[], sqlite3.Connection]


def format_file_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f}{unit}" if unit != "B" else f"{int(size)}B"
        size /= 1024
    return f"{size_bytes}B"


def sync_job_report_files(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    user_id: int,
    username: str,
    report_date: str,
    generated_files: list[str],
    created_at: str,
    local_tz: timezone,
) -> None:
    conn.execute("DELETE FROM report_files WHERE job_id = ?", (job_id,))
    rows: list[tuple[Any, ...]] = []
    for file_path in generated_files:
        path = Path(file_path)
        if path.suffix.lower() != ".docx" or not path.exists():
            continue
        stat = path.stat()
        rows.append(
            (
                job_id,
                user_id,
                username,
                report_date,
                path.name,
                str(path),
                stat.st_size,
                datetime.fromtimestamp(stat.st_mtime, tz=local_tz).strftime("%Y-%m-%d %H:%M:%S"),
                created_at,
            )
        )
    if rows:
        conn.executemany(
            """
            INSERT INTO report_files (
                job_id, user_id, username, report_date, file_name, file_path, file_size, modified_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def rebuild_report_file_index(*, db_connect: DbConnect, local_tz: timezone) -> None:
    conn = db_connect()
    rows = conn.execute(
        """
        SELECT jobs.id, jobs.user_id, jobs.created_at, jobs.generated_files, users.username
        FROM jobs JOIN users ON users.id = jobs.user_id
        WHERE jobs.generated_files IS NOT NULL AND jobs.generated_files != '[]'
        ORDER BY jobs.created_at DESC
        """
    ).fetchall()
    with conn:
        conn.execute("DELETE FROM report_files")
        for row in rows:
            created_at = datetime.fromisoformat(row["created_at"])
            generated_files = json.loads(row["generated_files"]) if row["generated_files"] else []
            sync_job_report_files(
                conn,
                job_id=row["id"],
                user_id=row["user_id"],
                username=row["username"],
                report_date=created_at.strftime("%Y-%m-%d"),
                generated_files=generated_files,
                created_at=row["created_at"],
                local_tz=local_tz,
            )
    conn.close()


def list_report_date_stats(*, db_connect: DbConnect) -> list[dict[str, Any]]:
    conn = db_connect()
    rows = conn.execute(
        """
        SELECT report_date, COUNT(*) AS count
        FROM report_files
        GROUP BY report_date
        ORDER BY report_date DESC
        """
    ).fetchall()
    conn.close()
    return [{"report_date": row["report_date"], "count": row["count"]} for row in rows]


def list_report_user_stats(*, db_connect: DbConnect, report_date: str) -> list[dict[str, Any]]:
    conn = db_connect()
    rows = conn.execute(
        """
        SELECT username, COUNT(*) AS count
        FROM report_files
        WHERE report_date = ?
        GROUP BY username
        ORDER BY username
        """,
        (report_date,),
    ).fetchall()
    conn.close()
    return [{"username": row["username"], "count": row["count"]} for row in rows]


def list_report_files_for_user(
    *,
    db_connect: DbConnect,
    report_date: str,
    username: str,
) -> list[dict[str, str]]:
    conn = db_connect()
    rows = conn.execute(
        """
        SELECT job_id, username, report_date, file_name, file_size, modified_at
        FROM report_files
        WHERE report_date = ? AND username = ?
        ORDER BY modified_at DESC, file_name
        """,
        (report_date, username),
    ).fetchall()
    conn.close()
    return [
        {
            "job_id": row["job_id"],
            "username": row["username"],
            "report_date": row["report_date"],
            "name": row["file_name"],
            "size": format_file_size(row["file_size"]),
            "modified_at": row["modified_at"],
        }
        for row in rows
    ]
