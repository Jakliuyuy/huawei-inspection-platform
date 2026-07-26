"""上传暂存会话。

上传与建任务分成两步：先落到 staging 目录并解析出逐系统完整度，用户
确认要生成哪些系统、报告日期是哪天之后，再建 job。

刻意不给 jobs 表加 prepared 状态：那会污染统计的 active 计数、重启恢复、
时间线和删除守卫共四处，而且用户上传后关掉页面就会留下永久僵尸任务。
独立 staging 配合转正时的原子 rename，现有的三套清理逻辑一行都不用改。
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from backend.config import config, now_local
from backend.db import db_connect
from core.log_layout import SystemStat, detect_log_root, preview_system_stats
from core.report_service import load_config

STAGING_DIRNAME = "_staging"
SESSION_TTL_HOURS = 2
MAX_STAGING_SESSIONS = 20


def staging_root() -> Path:
    return config.upload_dir / STAGING_DIRNAME


def new_upload_id() -> str:
    return f"u-{now_local().strftime('%Y%m%d')}-{secrets.token_hex(4)}"


@dataclass
class UploadPreview:
    upload_id: str
    log_root_label: str
    detected: bool
    log_file_count: int
    suggested_report_date: str
    systems: list[SystemStat]

    def to_payload(self, configs: dict) -> dict:
        return {
            "upload_id": self.upload_id,
            "log_root_label": self.log_root_label,
            "detected": self.detected,
            "log_file_count": self.log_file_count,
            "suggested_report_date": self.suggested_report_date,
            "systems": [
                {
                    "key": stat.key,
                    "display_name": stat.display_name,
                    "expected": stat.expected,
                    "actual": stat.actual,
                    "missing": stat.missing,
                    "has_logs": stat.has_logs,
                    "output_name_template": output_name_template(stat.key, configs.get(stat.key, {})),
                }
                for stat in self.systems
            ],
        }


def output_name_template(sys_key: str, info: dict) -> str:
    """报告文件名模板，{date} 由前端替换。

    命名规则的真相在 core/report_service.process_system；前端不要复刻，
    否则规则一变前端预览就骗人。
    """
    stem = sys_key if info.get("is_english_name") else info.get("display_name", sys_key)
    return f"{stem}{{date}}日巡检报告.docx"


def infer_report_date(log_root: Path) -> str:
    """从日志目录名推断报告日期。

    巡检日志绝大多数是跑前一日的，所以推断不出来时默认昨天而不是今天。
    """
    import re

    for name in (log_root.name, log_root.parent.name):
        m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", name) or re.search(r"(\d{4})(\d{2})(\d{2})", name)
        if m:
            year, month, day = (int(g) for g in m.groups())
            try:
                return f"{year:04d}-{month:02d}-{day:02d}"
            except ValueError:
                pass
    return (now_local() - timedelta(days=1)).strftime("%Y-%m-%d")


def analyze(upload_id: str, prepared_dir: Path) -> UploadPreview:
    configs = load_config(config.config_path)
    log_root = detect_log_root(prepared_dir, list(configs))
    detected = log_root is not None
    effective_root = log_root or prepared_dir
    stats = preview_system_stats(effective_root, configs)
    return UploadPreview(
        upload_id=upload_id,
        log_root_label=effective_root.name,
        detected=detected,
        log_file_count=sum(stat.actual for stat in stats),
        suggested_report_date=infer_report_date(effective_root),
        systems=stats,
    )


def create(user_id: int, upload_id: str, prepared_dir: Path, preview: UploadPreview) -> None:
    configs = load_config(config.config_path)
    created = now_local()
    conn = db_connect()
    with conn:
        conn.execute(
            """
            INSERT INTO upload_sessions (id, user_id, root_path, preview_json, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                upload_id,
                user_id,
                str(prepared_dir),
                json.dumps(preview.to_payload(configs), ensure_ascii=False),
                created.isoformat(),
                (created + timedelta(hours=SESSION_TTL_HOURS)).isoformat(),
            ),
        )
    conn.close()


def get(upload_id: str, user_id: int) -> sqlite3.Row | None:
    conn = db_connect()
    row = conn.execute(
        "SELECT * FROM upload_sessions WHERE id = ? AND user_id = ?",
        (upload_id, user_id),
    ).fetchone()
    conn.close()
    return row


def is_expired(row: sqlite3.Row) -> bool:
    return row["expires_at"] <= now_local().isoformat()


def drop(upload_id: str) -> None:
    """删除会话记录及其暂存目录。"""
    conn = db_connect()
    row = conn.execute("SELECT root_path FROM upload_sessions WHERE id = ?", (upload_id,)).fetchone()
    with conn:
        conn.execute("DELETE FROM upload_sessions WHERE id = ?", (upload_id,))
    conn.close()
    if row:
        _remove_session_dir(Path(row["root_path"]), upload_id)


def _remove_session_dir(prepared_dir: Path, upload_id: str) -> None:
    """回溯到 _staging/<upload_id> 整体删除，带双重校验避免误删。"""
    for candidate in (prepared_dir, *prepared_dir.parents):
        if candidate.name == upload_id and candidate.parent == staging_root():
            shutil.rmtree(candidate, ignore_errors=True)
            return


def promote(upload_id: str, job_id: str) -> Path:
    """把 staging 目录转成任务目录。

    同一个数据卷内 os.replace 是原子 rename、零拷贝；转正后磁盘布局与
    直接上传完全一致，delete_job_storage / cleanup_expired_data 无需改动。
    """
    source = staging_root() / upload_id
    target = config.upload_dir / job_id
    os.replace(source, target)
    conn = db_connect()
    with conn:
        conn.execute("DELETE FROM upload_sessions WHERE id = ?", (upload_id,))
    conn.close()
    return target / "prepared"


def collect_garbage() -> None:
    """清掉过期会话，以及数量超限时最旧的那些。"""
    conn = db_connect()
    expired = conn.execute(
        "SELECT id, root_path FROM upload_sessions WHERE expires_at <= ?",
        (now_local().isoformat(),),
    ).fetchall()
    surplus = conn.execute(
        "SELECT id, root_path FROM upload_sessions ORDER BY created_at DESC LIMIT -1 OFFSET ?",
        (MAX_STAGING_SESSIONS,),
    ).fetchall()
    stale = {row["id"]: row["root_path"] for row in (*expired, *surplus)}
    if stale:
        with conn:
            conn.executemany(
                "DELETE FROM upload_sessions WHERE id = ?", [(key,) for key in stale]
            )
    conn.close()
    for upload_id, root_path in stale.items():
        _remove_session_dir(Path(root_path), upload_id)

    # 数据库里没有记录、但磁盘上还在的目录（进程被杀等）一并清掉
    root = staging_root()
    if not root.exists():
        return
    conn = db_connect()
    known = {row["id"] for row in conn.execute("SELECT id FROM upload_sessions").fetchall()}
    conn.close()
    for path in root.iterdir():
        if path.is_dir() and path.name not in known:
            shutil.rmtree(path, ignore_errors=True)
