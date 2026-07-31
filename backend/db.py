"""数据库连接、建表与运行期维护。"""

from __future__ import annotations

import secrets
import sqlite3

from backend.config import LOCAL_USERNAME, config, now_local
from backend.persistence import cleanup_expired_data as cleanup_expired_data_impl
from backend.persistence import recover_incomplete_jobs as recover_incomplete_jobs_impl
from backend.security import hash_password

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS announcements (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    content TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    status_detail TEXT,
    input_path TEXT NOT NULL,
    output_path TEXT,
    bundle_path TEXT,
    log_root TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    error_message TEXT,
    generated_files TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    detail TEXT NOT NULL,
    ip_address TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS report_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    report_date TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL UNIQUE,
    file_size INTEGER NOT NULL,
    modified_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS upload_sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    root_path TEXT NOT NULL,
    preview_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS inspection_systems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    system_key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    current_version_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (current_version_id) REFERENCES inspection_system_versions (id)
);

CREATE TABLE IF NOT EXISTS inspection_system_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    system_id INTEGER NOT NULL,
    version INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'built', 'validating', 'validated', 'published', 'retired')),
    source_mode TEXT NOT NULL DEFAULT 'create',
    config_json TEXT NOT NULL,
    recipients_json TEXT NOT NULL DEFAULT '[]',
    template_path TEXT NOT NULL,
    template_sha256 TEXT,
    vbs_path TEXT,
    vbs_sha256 TEXT,
    validation_json TEXT,
    created_by INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (system_id, version),
    FOREIGN KEY (system_id) REFERENCES inspection_systems (id),
    FOREIGN KEY (created_by) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS log_batches (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    system_version_id INTEGER,
    status TEXT NOT NULL CHECK (status IN ('collecting', 'invalid', 'validated')),
    root_path TEXT NOT NULL,
    manifest_json TEXT,
    validation_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (system_version_id) REFERENCES inspection_system_versions (id)
);

CREATE TABLE IF NOT EXISTS log_batch_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (batch_id, file_name),
    FOREIGN KEY (batch_id) REFERENCES log_batches (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_upload_sessions_expires_at ON upload_sessions (expires_at);
CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions (token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions (expires_at);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_user_id_created_at ON jobs (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_finished_at ON jobs (finished_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id_created_at ON audit_logs (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_report_files_report_date ON report_files (report_date DESC);
CREATE INDEX IF NOT EXISTS idx_report_files_report_date_username ON report_files (report_date, username);
CREATE INDEX IF NOT EXISTS idx_report_files_job_id ON report_files (job_id);
CREATE INDEX IF NOT EXISTS idx_system_versions_system_id ON inspection_system_versions (system_id, version DESC);
CREATE INDEX IF NOT EXISTS idx_log_batches_user_id ON log_batches (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_log_batch_files_batch_id ON log_batch_files (batch_id);
"""


# 表名 -> [(列名, 列定义)]。只允许追加**可空**列，这样新镜像能读旧库、
# 旧镜像也能读新库（多出来的列被忽略），回滚时数据库不必一起回滚。
ADDED_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "jobs": [
        ("progress", "INTEGER NOT NULL DEFAULT 0"),
        ("status_detail", "TEXT"),
        ("report_date", "TEXT"),
        ("selected_systems", "TEXT"),
        ("log_batch_id", "TEXT"),
        ("locked_versions", "TEXT"),
    ],
}


def _add_missing_columns(conn: sqlite3.Connection) -> None:
    for table, columns in ADDED_COLUMNS.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for name, definition in columns:
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def ensure_dirs() -> None:
    for path in (
        config.data_root,
        config.runtime_dir,
        config.upload_dir,
        config.report_dir,
        config.system_artifact_dir,
        config.log_batch_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.database_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database() -> None:
    ensure_dirs()
    conn = db_connect()
    with conn:
        conn.executescript(SCHEMA)
        _add_missing_columns(conn)
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if user_count == 0:
            conn.execute(
                "INSERT INTO users (username, password_hash, is_admin, created_at) VALUES (?, ?, 1, ?)",
                (config.default_admin_username, hash_password(config.default_admin_password), now_local().isoformat()),
            )
        if config.local_mode and conn.execute(
            "SELECT id FROM users WHERE username = ?", (LOCAL_USERNAME,)
        ).fetchone() is None:
            # 本地模式免登录，但仍需一行真实用户承接 jobs.user_id 的外键
            conn.execute(
                "INSERT INTO users (username, password_hash, is_admin, created_at) VALUES (?, ?, 1, ?)",
                (LOCAL_USERNAME, hash_password(secrets.token_urlsafe(32)), now_local().isoformat()),
            )
        if conn.execute("SELECT id FROM announcements WHERE id = 1").fetchone() is None:
            conn.execute(
                "INSERT INTO announcements (id, content, updated_at, updated_by) VALUES (1, ?, ?, ?)",
                ("系统已部署，可开始上传巡检日志生成报告。", now_local().isoformat(), "system"),
            )
    conn.close()


def cleanup_expired_data() -> None:
    cleanup_expired_data_impl(db_connect=db_connect, now_local=now_local, retention_days=config.retention_days)


def recover_incomplete_jobs() -> None:
    recover_incomplete_jobs_impl(db_connect=db_connect, now_local=now_local)
