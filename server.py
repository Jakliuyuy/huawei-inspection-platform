from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import shutil
import sqlite3
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from core.report_service import ReportPaths, generate_reports

if load_dotenv is not None:
    load_dotenv(Path(__file__).resolve().parent / ".env")

APP_TITLE = "华为巡检云平台"
SESSION_COOKIE = "inspection_session"
LOCAL_TZ = timezone(timedelta(hours=8))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(200 * 1024 * 1024)))
LOGIN_WINDOW_SECONDS = 300
LOGIN_MAX_FAILURES = 5


@dataclass
class AppConfig:
    app_root: Path
    data_root: Path
    runtime_dir: Path
    upload_dir: Path
    report_dir: Path
    template_dir: Path
    config_path: Path
    database_path: Path
    session_hours: int
    retention_days: int
    default_admin_username: str
    default_admin_password: str
    max_job_workers: int
    secure_cookies: bool


def build_config() -> AppConfig:
    app_root = Path(__file__).resolve().parent
    data_root = Path(os.getenv("DATA_ROOT", app_root / "data")).resolve()
    runtime_dir = data_root / "runtime"
    upload_dir = data_root / "uploads"
    report_dir = data_root / "reports"
    template_dir = Path(os.getenv("TEMPLATE_DIR", app_root / "assets" / "templates")).resolve()
    config_path = Path(os.getenv("REPORT_CONFIG_PATH", app_root / "config" / "report.json")).resolve()
    database_path = runtime_dir / "app.db"
    return AppConfig(
        app_root=app_root,
        data_root=data_root,
        runtime_dir=runtime_dir,
        upload_dir=upload_dir,
        report_dir=report_dir,
        template_dir=template_dir,
        config_path=config_path,
        database_path=database_path,
        session_hours=int(os.getenv("SESSION_HOURS", "12")),
        retention_days=int(os.getenv("RETENTION_DAYS", "30")),
        default_admin_username=os.getenv("DEFAULT_ADMIN_USERNAME", "admin"),
        default_admin_password=os.getenv("DEFAULT_ADMIN_PASSWORD", "ChangeMe123!"),
        max_job_workers=max(1, int(os.getenv("MAX_JOB_WORKERS", "2"))),
        secure_cookies=os.getenv("SECURE_COOKIES", "true").lower() == "true",
    )


app = FastAPI(title=APP_TITLE)
config = build_config()
job_executor = ThreadPoolExecutor(max_workers=config.max_job_workers)
login_attempts: dict[str, list[float]] = {}
API_PREFIX = "/api"
STATUS_LABELS = {
    "queued": "排队中",
    "running": "处理中",
    "completed": "已完成",
    "failed": "失败",
}


def now_local() -> datetime:
    return datetime.now(tz=LOCAL_TZ)


def ensure_dirs() -> None:
    for path in (config.data_root, config.runtime_dir, config.upload_dir, config.report_dir):
        path.mkdir(parents=True, exist_ok=True)


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.database_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    salt, _, _ = encoded.partition("$")
    candidate = hash_password(password, salt)
    return hmac.compare_digest(candidate, encoded)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def initialize_database() -> None:
    ensure_dirs()
    conn = db_connect()
    with conn:
        conn.executescript(
            """
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
            """
        )
        job_columns = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        if "progress" not in job_columns:
            conn.execute("ALTER TABLE jobs ADD COLUMN progress INTEGER NOT NULL DEFAULT 0")
        if "status_detail" not in job_columns:
            conn.execute("ALTER TABLE jobs ADD COLUMN status_detail TEXT")
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if user_count == 0:
            conn.execute(
                "INSERT INTO users (username, password_hash, is_admin, created_at) VALUES (?, ?, 1, ?)",
                (config.default_admin_username, hash_password(config.default_admin_password), now_local().isoformat()),
            )
        if conn.execute("SELECT id FROM announcements WHERE id = 1").fetchone() is None:
            conn.execute(
                "INSERT INTO announcements (id, content, updated_at, updated_by) VALUES (1, ?, ?, ?)",
                ("系统已部署，可开始上传巡检日志生成报告。", now_local().isoformat(), "system"),
            )
    conn.close()


def cleanup_expired_data() -> None:
    cutoff = now_local() - timedelta(days=config.retention_days)
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


def record_audit(user_id: int | None, action: str, detail: str, request: Request | None = None) -> None:
    ip = request.client.host if request and request.client else ""
    conn = db_connect()
    with conn:
        conn.execute(
            "INSERT INTO audit_logs (user_id, action, detail, ip_address, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, action, detail, ip, now_local().isoformat()),
        )
    conn.close()


def get_user_by_username(username: str) -> sqlite3.Row | None:
    conn = db_connect()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return row


def get_user_by_session(token: str | None) -> sqlite3.Row | None:
    if not token:
        return None
    conn = db_connect()
    row = conn.execute(
        """
        SELECT users.* FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token_hash = ? AND sessions.expires_at > ?
        """,
        (hash_token(token), now_local().isoformat()),
    ).fetchone()
    conn.close()
    return row


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = now_local() + timedelta(hours=config.session_hours)
    conn = db_connect()
    with conn:
        conn.execute(
            "INSERT INTO sessions (user_id, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (user_id, hash_token(token), expires_at.isoformat(), now_local().isoformat()),
        )
        conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now_local().isoformat(), user_id))
    conn.close()
    return token


def clear_session(token: str | None) -> None:
    if not token:
        return
    conn = db_connect()
    with conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))
    conn.close()


def clear_user_sessions(user_id: int) -> None:
    conn = db_connect()
    with conn:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.close()


def require_user(request: Request) -> sqlite3.Row:
    user = get_user_by_session(request.cookies.get(SESSION_COOKIE))
    if not user:
        raise HTTPException(status_code=401, detail="未登录或会话已失效")
    return user


def require_admin(request: Request) -> sqlite3.Row:
    user = require_user(request)
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def should_rate_limit(ip: str) -> bool:
    now_ts = now_local().timestamp()
    attempts = [ts for ts in login_attempts.get(ip, []) if now_ts - ts < LOGIN_WINDOW_SECONDS]
    login_attempts[ip] = attempts
    return len(attempts) >= LOGIN_MAX_FAILURES


def note_login_failure(ip: str) -> None:
    login_attempts.setdefault(ip, []).append(now_local().timestamp())


def clear_login_failures(ip: str) -> None:
    login_attempts.pop(ip, None)


def issue_session_response(target: Response, token: str) -> Response:
    target.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=config.session_hours * 3600,
        secure=config.secure_cookies,
    )
    return target


def clear_session_response(target: Response) -> Response:
    target.delete_cookie(SESSION_COOKIE)
    return target


def announcement_text() -> str:
    conn = db_connect()
    row = conn.execute("SELECT content FROM announcements WHERE id = 1").fetchone()
    conn.close()
    return row["content"] if row else ""


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


def list_jobs(user: sqlite3.Row) -> list[sqlite3.Row]:
    conn = db_connect()
    if user["is_admin"]:
        rows = conn.execute(
            """
            SELECT jobs.*, users.username
            FROM jobs JOIN users ON users.id = jobs.user_id
            ORDER BY jobs.created_at DESC
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT jobs.*, users.username
            FROM jobs JOIN users ON users.id = jobs.user_id
            WHERE jobs.user_id = ?
            ORDER BY jobs.created_at DESC
            """,
            (user["id"],),
        ).fetchall()
    conn.close()
    return rows


def generate_job_id() -> str:
    date_prefix = now_local().strftime("%Y%m%d")
    conn = db_connect()
    row = conn.execute(
        """
        SELECT id FROM jobs
        WHERE id LIKE ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (f"{date_prefix}-%",),
    ).fetchone()
    conn.close()
    if not row:
        return f"{date_prefix}-001"
    _, _, suffix = row["id"].partition("-")
    sequence = int(suffix) + 1 if suffix.isdigit() else 1
    return f"{date_prefix}-{sequence:03d}"


def format_file_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f}{unit}" if unit != "B" else f"{int(size)}B"
        size /= 1024
    return f"{size_bytes}B"


def list_report_records() -> list[dict[str, str]]:
    conn = db_connect()
    rows = conn.execute(
        """
        SELECT jobs.id, jobs.created_at, jobs.generated_files, users.username
        FROM jobs JOIN users ON users.id = jobs.user_id
        WHERE jobs.generated_files IS NOT NULL AND jobs.generated_files != '[]'
        ORDER BY jobs.created_at DESC
        """
    ).fetchall()
    conn.close()

    records: list[dict[str, str]] = []
    for row in rows:
        created_at = datetime.fromisoformat(row["created_at"])
        report_date = created_at.strftime("%Y-%m-%d")
        generated_files = json.loads(row["generated_files"]) if row["generated_files"] else []
        for file_path in generated_files:
            path = Path(file_path)
            if path.suffix.lower() != ".docx" or not path.exists():
                continue
            stat = path.stat()
            records.append(
                {
                    "job_id": row["id"],
                    "username": row["username"],
                    "report_date": report_date,
                    "name": path.name,
                    "size": format_file_size(stat.st_size),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
    return records


def delete_job_storage(job: sqlite3.Row) -> None:
    for field in ("input_path", "output_path", "bundle_path"):
        value = job[field]
        if not value:
            continue
        path = Path(value)
        if path.is_file():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            shutil.rmtree(path, ignore_errors=True)


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


def sanitize_member_name(name: str) -> str:
    normalized = Path(name.replace("\\", "/"))
    if normalized.is_absolute() or ".." in normalized.parts:
        raise HTTPException(status_code=400, detail="压缩包中包含非法路径")
    return str(normalized)


def extract_zip_safe(zip_path: Path, target_dir: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            member_name = sanitize_member_name(member.filename)
            destination = target_dir / member_name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            with archive.open(member) as source, destination.open("wb") as handle:
                shutil.copyfileobj(source, handle)


def is_supported_upload(path: Path) -> bool:
    return path.suffix.lower() in {".zip", ".log"}


def copy_uploaded_logs(saved_files: list[Path], target_dir: Path) -> bool:
    log_files = [path for path in saved_files if path.suffix.lower() == ".log"]
    if not log_files:
        return False

    has_nested_layout = any(len(path.relative_to(target_dir.parent / "input").parts) > 1 for path in log_files)
    if has_nested_layout:
        for log_file in log_files:
            relative_path = log_file.relative_to(target_dir.parent / "input")
            destination = target_dir / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(log_file, destination)
        return True

    date_dir = target_dir / now_local().strftime("%Y-%m-%d")
    date_dir.mkdir(parents=True, exist_ok=True)
    for log_file in log_files:
        shutil.copy2(log_file, date_dir / log_file.name)
    return True


def detect_log_root(path: Path) -> Path:
    candidates = [path]
    candidates.extend(child for child in path.iterdir() if child.is_dir())
    for candidate in candidates:
        if any((candidate / name).exists() for name in ["TOC", "TOB", "NM1", "NM2", "NM3", "Softswitch", "SMS", "GPRS", "IntelligentNet"]):
            return candidate
    date_dirs = sorted(child for child in path.rglob("*") if child.is_dir() and "-" in child.name)
    if date_dirs:
        return date_dirs[0]
    raise HTTPException(status_code=400, detail="无法识别日志目录结构")


def create_bundle(output_dir: Path, bundle_path: Path) -> None:
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in output_dir.rglob("*"):
            if file.is_file() and file != bundle_path:
                archive.write(file, arcname=file.relative_to(output_dir))


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def clamp_progress(value: int | None) -> int:
    if value is None:
        return 0
    return max(0, min(100, int(value)))


def update_job(job_id: str, **fields: Any) -> None:
    if not fields:
        return
    columns = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [job_id]
    conn = db_connect()
    with conn:
        conn.execute(f"UPDATE jobs SET {columns} WHERE id = ?", values)
    conn.close()


def process_job(job_id: str, user_id: int) -> None:
    try:
        cleanup_expired_data()
        conn = db_connect()
        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        conn.close()
        if not job:
            return

        input_path = Path(job["input_path"])
        output_dir = config.report_dir / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        update_job(
            job_id,
            status="running",
            progress=5,
            status_detail="正在识别日志目录",
            started_at=now_local().isoformat(),
        )

        log_root = detect_log_root(input_path)

        def report_progress(completed_count: int, total_count: int, sys_key: str, sys_info: dict[str, Any]) -> None:
            base = 10
            span = 80
            progress = base + round((completed_count / max(total_count, 1)) * span)
            update_job(
                job_id,
                progress=progress,
                status_detail=f"正在生成 {sys_info['display_name']}（{completed_count}/{total_count}）",
            )

        update_job(job_id, progress=10, status_detail="已识别日志目录，开始生成报告")
        summary = generate_reports(
            paths=ReportPaths(
                root=config.app_root,
                config_path=config.config_path,
                logs_base=log_root.parent if log_root.parent.exists() else input_path,
                templates_dir=config.template_dir,
                output_base=output_dir,
            ),
            log_root=log_root,
            output_dir=output_dir,
            target_date=now_local().strftime("%Y-%m-%d"),
            max_workers=max(1, config.max_job_workers),
            progress_callback=report_progress,
        )
        update_job(job_id, progress=95, status_detail="正在打包结果文件")
        bundle_path = output_dir / f"{job_id}.zip"
        create_bundle(output_dir, bundle_path)
        update_job(
            job_id,
            status="completed",
            progress=100,
            status_detail="报告生成完成",
            output_path=str(output_dir),
            bundle_path=str(bundle_path),
            log_root=summary.log_root,
            finished_at=now_local().isoformat(),
            generated_files=json.dumps(summary.generated_files, ensure_ascii=False),
            error_message=None,
        )
        record_audit(user_id, "job_completed", f"任务 {job_id} 完成，生成 {len(summary.generated_files)} 个文件")
    except Exception as exc:
        update_job(
            job_id,
            status="failed",
            progress=100,
            status_detail="任务执行失败",
            finished_at=now_local().isoformat(),
            error_message=str(exc),
        )
        record_audit(user_id, "job_failed", f"任务 {job_id} 失败: {exc}")


def enqueue_job(job_id: str, user_id: int) -> None:
    job_executor.submit(process_job, job_id, user_id)


def save_uploads(job_dir: Path, files: list[UploadFile]) -> Path:
    input_dir = job_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    total_size = 0
    saved_files: list[Path] = []
    for upload in files:
        if not upload.filename:
            continue
        relative_name = sanitize_member_name(upload.filename)
        relative_path = Path(relative_name)
        if not is_supported_upload(relative_path):
            raise HTTPException(status_code=400, detail=f"不支持的文件类型: {upload.filename}")
        target = input_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as handle:
            while chunk := upload.file.read(1024 * 1024):
                total_size += len(chunk)
                if total_size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=400, detail="上传文件总大小超出限制")
                handle.write(chunk)
        saved_files.append(target)

    prepared_dir = job_dir / "prepared"
    prepared_dir.mkdir(parents=True, exist_ok=True)

    zip_files = [path for path in saved_files if path.suffix.lower() == ".zip"]
    copied_logs = copy_uploaded_logs(saved_files, prepared_dir)
    for zip_file in zip_files:
        extract_zip_safe(zip_file, prepared_dir)

    if zip_files or copied_logs:
        return prepared_dir
    raise HTTPException(status_code=400, detail="未发现可处理的日志文件")


def list_admin_users() -> list[sqlite3.Row]:
    conn = db_connect()
    rows = conn.execute("SELECT id, username, is_admin, created_at, last_login_at FROM users ORDER BY created_at").fetchall()
    conn.close()
    return rows


def list_admin_jobs(limit: int = 100) -> list[sqlite3.Row]:
    conn = db_connect()
    rows = conn.execute(
        """
        SELECT jobs.*, users.username
        FROM jobs JOIN users ON users.id = jobs.user_id
        ORDER BY jobs.created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return rows


def list_audits_page(page: int, page_size: int) -> tuple[list[sqlite3.Row], int]:
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


@app.post(f"{API_PREFIX}/auth/login")
async def api_login(request: Request) -> JSONResponse:
    payload = await request.json()
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    ip = request.client.host if request.client else "unknown"
    if should_rate_limit(ip):
        raise HTTPException(status_code=429, detail="登录失败次数过多，请稍后再试")
    user = get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        note_login_failure(ip)
        record_audit(None, "login_failed", f"用户名 {username} 登录失败", request)
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    clear_login_failures(ip)
    token = create_session(user["id"])
    record_audit(user["id"], "login", "用户登录成功", request)
    response = JSONResponse({"ok": True, "user": serialize_user(user)})
    return issue_session_response(response, token)


@app.post(f"{API_PREFIX}/auth/logout")
async def api_logout(request: Request) -> JSONResponse:
    token = request.cookies.get(SESSION_COOKIE)
    user = get_user_by_session(token)
    if user:
        record_audit(user["id"], "logout", "用户退出登录", request)
    clear_session(token)
    response = JSONResponse({"ok": True})
    return clear_session_response(response)


@app.get(f"{API_PREFIX}/auth/me")
async def api_me(request: Request) -> JSONResponse:
    user = require_user(request)
    return JSONResponse(serialize_user(user))


@app.get(f"{API_PREFIX}/announcements")
async def api_announcements() -> JSONResponse:
    return JSONResponse({"content": announcement_text()})


@app.get(f"{API_PREFIX}/jobs")
async def api_jobs(request: Request) -> JSONResponse:
    user = require_user(request)
    rows = list_jobs(user)
    return JSONResponse([serialize_job(row) for row in rows])


@app.post(f"{API_PREFIX}/jobs")
async def api_create_job(request: Request, files: list[UploadFile] = File(...)) -> JSONResponse:
    user = require_user(request)
    cleanup_expired_data()
    if not files:
        raise HTTPException(status_code=400, detail="至少上传一个文件")
    job_id = generate_job_id()
    job_dir = config.upload_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    input_path = save_uploads(job_dir, files)
    conn = db_connect()
    with conn:
        conn.execute(
            """
            INSERT INTO jobs (id, user_id, status, progress, status_detail, input_path, created_at, generated_files)
            VALUES (?, ?, 'queued', 0, '等待工作线程处理', ?, ?, '[]')
            """,
            (job_id, user["id"], str(input_path), now_local().isoformat()),
        )
    conn.close()
    record_audit(user["id"], "job_created", f"创建任务 {job_id}", request)
    enqueue_job(job_id, user["id"])
    return JSONResponse({"ok": True, "job_id": job_id})


@app.get(f"{API_PREFIX}/jobs/{{job_id}}")
async def api_job_detail(request: Request, job_id: str) -> JSONResponse:
    user = require_user(request)
    job = ensure_job_access(get_job(job_id), user)
    return JSONResponse(serialize_job(job))


@app.get(f"{API_PREFIX}/jobs/{{job_id}}/download")
async def api_download_job(request: Request, job_id: str) -> FileResponse:
    user = require_user(request)
    job = ensure_job_access(get_job(job_id), user)
    if not job["bundle_path"]:
        raise HTTPException(status_code=404, detail="任务结果尚未生成")
    path = Path(job["bundle_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="结果文件不存在")
    record_audit(user["id"], "download_bundle", f"下载任务 {job_id} 结果", request)
    return FileResponse(path, filename=path.name)


@app.get(f"{API_PREFIX}/jobs/{{job_id}}/files/{{file_name}}")
async def api_download_job_file(request: Request, job_id: str, file_name: str) -> FileResponse:
    user = require_user(request)
    job = ensure_job_access(get_job(job_id), user)
    if not job["output_path"]:
        raise HTTPException(status_code=404, detail="任务结果尚未生成")
    path = Path(job["output_path"]) / file_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    record_audit(user["id"], "download_file", f"下载任务 {job_id} 文件 {file_name}", request)
    return FileResponse(path, filename=file_name)


@app.get(f"{API_PREFIX}/admin/users")
async def api_admin_users(request: Request) -> JSONResponse:
    require_admin(request)
    return JSONResponse([serialize_user(row) for row in list_admin_users()])


@app.post(f"{API_PREFIX}/admin/users")
async def api_admin_create_user(request: Request) -> JSONResponse:
    admin = require_admin(request)
    payload = await request.json()
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    is_admin = int(bool(payload.get("is_admin", False)))
    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")
    if get_user_by_username(username):
        raise HTTPException(status_code=400, detail="用户名已存在")
    conn = db_connect()
    with conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at) VALUES (?, ?, ?, ?)",
            (username, hash_password(password), is_admin, now_local().isoformat()),
        )
    conn.close()
    record_audit(admin["id"], "user_created", f"创建用户 {username}", request)
    return JSONResponse({"ok": True})


@app.put(f"{API_PREFIX}/admin/users/{{target_user_id}}/password")
async def api_admin_reset_password(request: Request, target_user_id: int) -> JSONResponse:
    admin = require_admin(request)
    payload = await request.json()
    new_password = str(payload.get("new_password", "")).strip()
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="新密码长度不能少于 8 位")
    conn = db_connect()
    target_user = conn.execute("SELECT id, username FROM users WHERE id = ?", (target_user_id,)).fetchone()
    if not target_user:
        conn.close()
        raise HTTPException(status_code=404, detail="用户不存在")
    with conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new_password), target_user_id))
    conn.close()
    clear_user_sessions(target_user_id)
    record_audit(admin["id"], "password_reset", f"管理员重置用户 {target_user['username']} 的密码", request)
    return JSONResponse({"ok": True})


@app.put(f"{API_PREFIX}/admin/announcement")
async def api_update_announcement(request: Request) -> JSONResponse:
    user = require_admin(request)
    payload = await request.json()
    content = str(payload.get("content", "")).strip()
    if not content:
        raise HTTPException(status_code=400, detail="公告内容不能为空")
    conn = db_connect()
    with conn:
        conn.execute(
            "UPDATE announcements SET content = ?, updated_at = ?, updated_by = ? WHERE id = 1",
            (content, now_local().isoformat(), user["username"]),
        )
    conn.close()
    record_audit(user["id"], "announcement_updated", "更新系统公告", request)
    return JSONResponse({"ok": True, "content": content})


@app.get(f"{API_PREFIX}/admin/jobs")
async def api_admin_jobs(request: Request) -> JSONResponse:
    require_admin(request)
    return JSONResponse([serialize_job(row) for row in list_admin_jobs()])


@app.delete(f"{API_PREFIX}/admin/jobs/{{job_id}}")
async def api_admin_delete_job(request: Request, job_id: str) -> JSONResponse:
    admin = require_admin(request)
    conn = db_connect()
    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not job:
        conn.close()
        raise HTTPException(status_code=404, detail="任务不存在")
    if job["status"] in {"queued", "running"}:
        conn.close()
        raise HTTPException(status_code=400, detail="处理中任务不可删除")
    with conn:
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.close()
    delete_job_storage(job)
    record_audit(admin["id"], "job_deleted", f"管理员删除任务 {job_id}", request)
    return JSONResponse({"ok": True})


@app.get(f"{API_PREFIX}/admin/reports/dates")
async def api_report_dates(request: Request) -> JSONResponse:
    require_admin(request)
    report_records = list_report_records()
    dates = sorted({item["report_date"] for item in report_records}, reverse=True)
    items = [
        {
            "report_date": date,
            "count": sum(1 for item in report_records if item["report_date"] == date),
        }
        for date in dates
    ]
    return JSONResponse(items)


@app.get(f"{API_PREFIX}/admin/reports/users")
async def api_report_users(request: Request, date: str) -> JSONResponse:
    require_admin(request)
    report_records = list_report_records()
    users = sorted({item["username"] for item in report_records if item["report_date"] == date})
    items = [
        {
            "username": username,
            "count": sum(
                1 for item in report_records if item["report_date"] == date and item["username"] == username
            ),
        }
        for username in users
    ]
    return JSONResponse(items)


@app.get(f"{API_PREFIX}/admin/reports/files")
async def api_report_files(request: Request, date: str, user: str) -> JSONResponse:
    require_admin(request)
    report_records = list_report_records()
    items = [
        {
            **item,
            "download_url": f"{API_PREFIX}/admin/reports/{item['job_id']}/{item['name']}/download",
        }
        for item in report_records
        if item["report_date"] == date and item["username"] == user
    ]
    return JSONResponse(items)


@app.get(f"{API_PREFIX}/admin/reports/{{job_id}}/{{file_name}}/download")
async def api_admin_download_report(request: Request, job_id: str, file_name: str) -> FileResponse:
    admin = require_admin(request)
    path = resolve_admin_report_path(job_id, file_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="报告文件不存在")
    record_audit(admin["id"], "report_download", f"管理员下载报告 {path.name}", request)
    return FileResponse(path, filename=path.name)


@app.delete(f"{API_PREFIX}/admin/reports/{{job_id}}/{{file_name}}")
async def api_admin_delete_report(request: Request, job_id: str, file_name: str) -> JSONResponse:
    admin = require_admin(request)
    path = resolve_admin_report_path(job_id, file_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="报告文件不存在")
    path.unlink(missing_ok=True)
    conn = db_connect()
    job = conn.execute("SELECT generated_files FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if job:
        generated_files = json.loads(job["generated_files"]) if job["generated_files"] else []
        filtered_files = [item for item in generated_files if Path(item).name != path.name]
        with conn:
            conn.execute(
                "UPDATE jobs SET generated_files = ? WHERE id = ?",
                (json.dumps(filtered_files, ensure_ascii=False), job_id),
            )
    conn.close()
    parent = path.parent
    if parent.exists() and not any(parent.iterdir()):
        parent.rmdir()
    record_audit(admin["id"], "report_deleted", f"管理员删除报告 {path.name}", request)
    return JSONResponse({"ok": True})


@app.get(f"{API_PREFIX}/admin/audits")
async def api_admin_audits(request: Request, page: int = 1, page_size: int = 20) -> JSONResponse:
    require_admin(request)
    safe_page = max(1, page)
    safe_page_size = max(1, min(100, page_size))
    audits, total = list_audits_page(safe_page, safe_page_size)
    total_pages = max(1, ceil(total / safe_page_size))
    return JSONResponse(
        {
            "items": [serialize_audit(item) for item in audits],
            "page": safe_page,
            "page_size": safe_page_size,
            "total": total,
            "total_pages": total_pages,
        }
    )


@app.get(f"{API_PREFIX}/health")
async def api_health() -> JSONResponse:
    return JSONResponse({"status": "ok", "time": now_local().isoformat()})


@app.on_event("startup")
def startup_event() -> None:
    initialize_database()
    cleanup_expired_data()


def spa_redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=302)


@app.get("/")
async def home(request: Request) -> RedirectResponse:
    user = get_user_by_session(request.cookies.get(SESSION_COOKIE))
    return spa_redirect("/app/dashboard" if user else "/app/login")


@app.get("/login")
async def login_page() -> RedirectResponse:
    return spa_redirect("/app/login")


@app.post("/login")
async def legacy_login_redirect() -> RedirectResponse:
    return spa_redirect("/app/login")


@app.get("/logout")
async def logout_page() -> RedirectResponse:
    return spa_redirect("/app/login")


@app.post("/logout")
async def legacy_logout_redirect(request: Request) -> Response:
    token = request.cookies.get(SESSION_COOKIE)
    user = get_user_by_session(token)
    if user:
        record_audit(user["id"], "logout", "用户退出登录", request)
    clear_session(token)
    return clear_session_response(spa_redirect("/app/login"))


@app.get("/dashboard")
async def dashboard_redirect() -> RedirectResponse:
    return spa_redirect("/app/dashboard")


@app.get("/upload")
async def upload_redirect() -> RedirectResponse:
    return spa_redirect("/app/tasks/new")


@app.get("/jobs/{job_id}")
async def job_detail_redirect(job_id: str) -> RedirectResponse:
    return spa_redirect(f"/app/tasks/{job_id}")


@app.get("/admin")
async def admin_redirect() -> RedirectResponse:
    return spa_redirect("/app/admin")


def resolve_admin_report_path(job_id: str, file_name: str) -> Path:
    path = (config.report_dir / job_id / Path(file_name).name).resolve()
    if config.report_dir not in path.parents:
        raise HTTPException(status_code=400, detail="非法文件路径")
    if path.suffix.lower() != ".docx":
        raise HTTPException(status_code=400, detail="仅允许管理 Word 报告")
    return path


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=int(os.getenv("PORT", "8080")), reload=False)
