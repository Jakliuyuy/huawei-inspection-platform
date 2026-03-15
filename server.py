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
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from core.report_service import ReportPaths, generate_reports
from frontend.views import (
    render_admin_page,
    render_dashboard_page,
    render_error_page,
    render_home_page,
    render_job_detail_page,
    render_progress,
    render_upload_page,
)

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
    template_dir = Path(os.getenv("TEMPLATE_DIR", app_root / "Word_模板库")).resolve()
    config_path = Path(os.getenv("REPORT_CONFIG_PATH", app_root / "config.json")).resolve()
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


def announcement_text() -> str:
    conn = db_connect()
    row = conn.execute("SELECT content FROM announcements WHERE id = 1").fetchone()
    conn.close()
    return row["content"] if row else ""


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


def list_generated_reports() -> list[dict[str, str]]:
    reports: list[dict[str, str]] = []
    if not config.report_dir.exists():
        return reports
    for path in sorted(config.report_dir.rglob("*.docx"), key=lambda item: item.stat().st_mtime, reverse=True):
        relative = path.relative_to(config.report_dir)
        parts = relative.parts
        job_id = parts[0] if parts else ""
        stat = path.stat()
        reports.append(
            {
                "job_id": job_id,
                "name": path.name,
                "relative_path": str(relative),
                "size": format_file_size(stat.st_size),
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    return reports


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


def status_tag_class(status: str) -> str:
    if status == "completed":
        return "done"
    if status == "failed":
        return "fail"
    return "wait"


def clamp_progress(value: int | None) -> int:
    if value is None:
        return 0
    return max(0, min(100, int(value)))


def build_job_timeline(job: sqlite3.Row) -> str:
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

    items: list[str] = []
    for index, (title, desc, active) in enumerate(steps, 1):
        state_class = "done" if active else "wait"
        items.append(
            f"""
            <li class="timeline-item {state_class}">
                <span class="timeline-dot">{index}</span>
                <div>
                    <strong>{title}</strong>
                    <p>{desc}</p>
                </div>
            </li>
            """
        )
    return f'<ol class="timeline">{"".join(items)}</ol>'


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


@app.on_event("startup")
def startup_event() -> None:
    initialize_database()
    cleanup_expired_data()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    user = get_user_by_session(request.cookies.get(SESSION_COOKIE))
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return render_home_page(APP_TITLE, announcement_text())


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)) -> Response:
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
    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=config.session_hours * 3600,
        secure=config.secure_cookies,
    )
    return response


@app.post("/logout")
async def logout(request: Request) -> Response:
    token = request.cookies.get(SESSION_COOKIE)
    user = get_user_by_session(token)
    if user:
        record_audit(user["id"], "logout", "用户退出登录", request)
    clear_session(token)
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    user = require_user(request)
    jobs = list_jobs(user)
    active_jobs = [job for job in jobs if job["status"] in {"queued", "running"}]
    completed_jobs = sum(1 for job in jobs if job["status"] == "completed")
    failed_jobs = sum(1 for job in jobs if job["status"] == "failed")
    rows = []
    for job in jobs:
        actions = [f'<a class="button secondary" href="/jobs/{job["id"]}">详情</a>']
        if user["is_admin"]:
            if job["status"] in {"completed", "failed"}:
                actions.append(
                    f'<form action="/admin/jobs/{job["id"]}/delete" method="post" onsubmit="return confirm(\'确认删除任务 {job["id"]} 吗？\');">'
                    f'<button type="submit" class="danger">删除</button>'
                    f"</form>"
                )
            else:
                actions.append('<span class="muted">处理中任务不可删除</span>')
        rows.append(
            f"""
            <tr>
                <td><a href="/jobs/{job['id']}">{job['id']}</a></td>
                <td>{job['username']}</td>
                <td><span class="tag {status_tag_class(job['status'])}">{status_label(job['status'])}</span></td>
                <td>{render_progress(job['progress'], job['status_detail'])}</td>
                <td>{job['created_at']}</td>
                <td>{job['finished_at'] or '-'}</td>
                <td><div class="inline-actions">{''.join(actions)}</div></td>
            </tr>
            """
        )
    return render_dashboard_page(
        user=user,
        rows_html="".join(rows),
        total_jobs=len(jobs),
        active_jobs=len(active_jobs),
        completed_jobs=completed_jobs,
        failed_jobs=failed_jobs,
        announcement=announcement_text(),
    )


@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request) -> HTMLResponse:
    user = require_user(request)
    return render_upload_page(user)


@app.post("/jobs")
async def create_job(request: Request, files: list[UploadFile] = File(...)) -> Response:
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
    return RedirectResponse(f"/jobs/{job_id}", status_code=302)


@app.get("/jobs", response_class=JSONResponse)
async def jobs_api(request: Request) -> JSONResponse:
    user = require_user(request)
    rows = list_jobs(user)
    return JSONResponse(
        [
            {
                "id": row["id"],
                "status": row["status"],
                "status_label": status_label(row["status"]),
                "progress": clamp_progress(row["progress"]),
                "status_detail": row["status_detail"] or "",
                "created_at": row["created_at"],
                "finished_at": row["finished_at"],
                "username": row["username"],
            }
            for row in rows
        ]
    )


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: str) -> HTMLResponse:
    user = require_user(request)
    job = ensure_job_access(get_job(job_id), user)
    generated_files = json.loads(job["generated_files"]) if job["generated_files"] else []
    file_links = []
    for file_path in generated_files:
        name = Path(file_path).name
        file_links.append(f'<li><a href="/jobs/{job_id}/files/{name}">{name}</a></li>')
    download = f'<a class="button" href="/jobs/{job_id}/download">下载任务结果</a>' if job["bundle_path"] else ""
    timeline = build_job_timeline(job)
    status_html = f'<span class="tag {status_tag_class(job["status"])}">{status_label(job["status"])}</span>'
    return render_job_detail_page(
        user=user,
        job_id=job["id"],
        username=job["username"],
        status_html=status_html,
        progress_html=render_progress(job["progress"], job["status_detail"]),
        created_at=job["created_at"],
        finished_at=job["finished_at"] or "-",
        log_root=job["log_root"] or "-",
        download_html=download,
        file_links_html="".join(file_links),
        error_message=job["error_message"] or "无",
        timeline_html=timeline,
        auto_refresh=job["status"] in {"queued", "running"},
    )


@app.get("/jobs/{job_id}/download")
async def download_job(request: Request, job_id: str) -> FileResponse:
    user = require_user(request)
    job = ensure_job_access(get_job(job_id), user)
    if not job["bundle_path"]:
        raise HTTPException(status_code=404, detail="任务结果尚未生成")
    path = Path(job["bundle_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="结果文件不存在")
    record_audit(user["id"], "download_bundle", f"下载任务 {job_id} 结果", request)
    return FileResponse(path, filename=path.name)


@app.get("/jobs/{job_id}/files/{file_name}")
async def download_job_file(request: Request, job_id: str, file_name: str) -> FileResponse:
    user = require_user(request)
    job = ensure_job_access(get_job(job_id), user)
    if not job["output_path"]:
        raise HTTPException(status_code=404, detail="任务结果尚未生成")
    path = Path(job["output_path"]) / file_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    record_audit(user["id"], "download_file", f"下载任务 {job_id} 文件 {file_name}", request)
    return FileResponse(path, filename=file_name)


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request) -> HTMLResponse:
    user = require_admin(request)
    admin_section = request.query_params.get("section", "users")
    if admin_section not in {"users", "jobs", "reports", "audits"}:
        admin_section = "users"
    selected_report_date = request.query_params.get("report_date", "").strip()
    selected_report_user = request.query_params.get("report_user", "").strip()
    audit_page_size = 20
    try:
        audit_page = max(1, int(request.query_params.get("audit_page", "1")))
    except ValueError:
        audit_page = 1
    audit_offset = (audit_page - 1) * audit_page_size
    conn = db_connect()
    users = conn.execute("SELECT id, username, is_admin, created_at, last_login_at FROM users ORDER BY created_at").fetchall()
    jobs = conn.execute(
        """
        SELECT jobs.*, users.username
        FROM jobs JOIN users ON users.id = jobs.user_id
        ORDER BY jobs.created_at DESC
        LIMIT 100
        """
    ).fetchall()
    audits = conn.execute(
        """
        SELECT audit_logs.*, users.username
        FROM audit_logs LEFT JOIN users ON users.id = audit_logs.user_id
        ORDER BY audit_logs.created_at DESC
        LIMIT ? OFFSET ?
        """
        ,
        (audit_page_size, audit_offset),
    ).fetchall()
    audit_total = conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
    conn.close()
    report_records = list_report_records()
    report_dates = sorted({item["report_date"] for item in report_records}, reverse=True)
    report_users = sorted({item["username"] for item in report_records if item["report_date"] == selected_report_date})
    filtered_reports = [
        item
        for item in report_records
        if item["report_date"] == selected_report_date and item["username"] == selected_report_user
    ]
    report_date_rows = "".join(
        f'<tr><td>{date}</td><td>{sum(1 for item in report_records if item["report_date"] == date)}</td><td><a class="button secondary" href="/admin?section=reports&report_date={date}">查看用户</a></td></tr>'
        for date in report_dates
    )
    report_user_rows = "".join(
        f'<tr><td>{name}</td><td>{sum(1 for item in report_records if item["report_date"] == selected_report_date and item["username"] == name)}</td><td><a class="button secondary" href="/admin?section=reports&report_date={selected_report_date}&report_user={name}">查看文档</a></td></tr>'
        for name in report_users
    )
    report_doc_rows = "".join(
        (
            f"<tr>"
            f"<td>{item['job_id']}</td>"
            f"<td>{item['name']}</td>"
            f"<td>{item['size']}</td>"
            f"<td>{item['modified_at']}</td>"
            f"<td><div class=\"inline-actions\">"
            f"<a class=\"button secondary\" href=\"/admin/reports/{item['job_id']}/{item['name']}/download\">下载</a>"
            f"<form action=\"/admin/reports/{item['job_id']}/{item['name']}/delete\" method=\"post\" onsubmit=\"return confirm('确认删除 {item['name']} 吗？');\">"
            f"<button type=\"submit\" class=\"danger\">删除</button>"
            f"</form>"
            f"</div></td>"
            f"</tr>"
        )
        for item in filtered_reports
    )
    report_breadcrumb_parts = ['<a href="/admin?section=reports">报告管理</a>']
    if selected_report_date:
        report_breadcrumb_parts.append(
            f'<a href="/admin?section=reports&report_date={selected_report_date}">{selected_report_date}</a>'
        )
    if selected_report_user:
        report_breadcrumb_parts.append(
            f'<span>{selected_report_user}</span>'
        )
    report_breadcrumb = f'<div class="crumbs">{" / ".join(report_breadcrumb_parts)}</div>'
    job_rows = "".join(
        (
            f"<tr>"
            f"<td>{item['id']}</td>"
            f"<td>{item['username']}</td>"
            f"<td>{status_label(item['status'])}</td>"
            f"<td>{item['created_at']}</td>"
            f"<td>{item['finished_at'] or '-'}</td>"
            f"<td><div class=\"inline-actions\">"
            f"<a class=\"button secondary\" href=\"/jobs/{item['id']}\">查看</a>"
            + (
                f"<form action=\"/admin/jobs/{item['id']}/delete\" method=\"post\" onsubmit=\"return confirm('确认删除任务 {item['id']} 吗？');\">"
                f"<button type=\"submit\" class=\"danger\">删除</button>"
                f"</form>"
                if item["status"] in {"completed", "failed"}
                else "<span class=\"muted\">处理中任务不可删除</span>"
            )
            + "</div></td></tr>"
        )
        for item in jobs
    )
    user_rows = "".join(
        (
            f"<tr>"
            f"<td>{item['username']}</td>"
            f"<td>{'管理员' if item['is_admin'] else '普通用户'}</td>"
            f"<td>{item['created_at']}</td>"
            f"<td>{item['last_login_at'] or '-'}</td>"
            f"<td><button type=\"button\" onclick=\"openModal('resetPasswordModal-{item['id']}')\">重置密码</button>"
            f"<div id=\"resetPasswordModal-{item['id']}\" class=\"modal\" onclick=\"closeModalOnBackdrop(event, 'resetPasswordModal-{item['id']}')\">"
            f"<div class=\"modal-panel\">"
            f"<div class=\"toolbar\"><div class=\"panel-title\"><h2>重置密码</h2><span class=\"eyebrow\">Password</span></div>"
            f"<button type=\"button\" class=\"modal-close\" onclick=\"closeModal('resetPasswordModal-{item['id']}')\">关闭</button></div>"
            f"<form action=\"/admin/users/{item['id']}/password\" method=\"post\">"
            f"<p>为用户 <strong>{item['username']}</strong> 设置新密码</p>"
            f"<label>新密码</label>"
            f"<input name=\"new_password\" type=\"password\" placeholder=\"输入新密码\" required>"
            f"<button type=\"submit\">确认重置</button>"
            f"</form></div></div></td>"
            f"</tr>"
        )
        for item in users
    )
    audit_rows = "".join(
        f"<tr><td>{item['created_at']}</td><td>{item['username'] or '匿名'}</td><td>{item['action']}</td><td>{item['detail']}</td></tr>"
        for item in audits
    )
    audit_total_pages = max(1, (audit_total + audit_page_size - 1) // audit_page_size)
    pagination_links: list[str] = []
    if audit_page > 1:
        pagination_links.append(f'<a class="button secondary" href="/admin?section=audits&audit_page={audit_page - 1}">上一页</a>')
    pagination_links.append(f'<span class="muted">第 {audit_page} / {audit_total_pages} 页，共 {audit_total} 条</span>')
    if audit_page < audit_total_pages:
        pagination_links.append(f'<a class="button secondary" href="/admin?section=audits&audit_page={audit_page + 1}">下一页</a>')
    audit_pagination = f'<div class="inline-actions">{"".join(pagination_links)}</div>'
    section_nav = """
    <div class="subnav">
        <a href="/admin?section=users" class="{users_class}">用户管理</a>
        <a href="/admin?section=jobs" class="{jobs_class}">任务管理</a>
        <a href="/admin?section=reports" class="{reports_class}">Word 报告</a>
        <a href="/admin?section=audits" class="{audits_class}">审计日志</a>
    </div>
    """.format(
        users_class="active" if admin_section == "users" else "",
        jobs_class="active" if admin_section == "jobs" else "",
        reports_class="active" if admin_section == "reports" else "",
        audits_class="active" if admin_section == "audits" else "",
    )

    users_section = f"""
    <div class="card">
        <div class="toolbar">
            <div class="panel-title">
                <h2>用户管理</h2>
                <span class="eyebrow">Accounts</span>
            </div>
            <button type="button" onclick="openModal('createUserModal')">新增用户</button>
        </div>
        <div class="table-wrap">
            <table><thead><tr><th>用户名</th><th>角色</th><th>创建时间</th><th>最后登录</th><th>密码管理</th></tr></thead><tbody>{user_rows}</tbody></table>
        </div>
    </div>
    <div class="card">
        <div class="panel-title">
            <h2>更新公告</h2>
            <span class="eyebrow">Notice</span>
        </div>
        <form action="/admin/announcement" method="post">
            <textarea name="content" rows="5" required>{announcement_text()}</textarea>
            <button type="submit">保存公告</button>
        </form>
    </div>
    <div id="createUserModal" class="modal" onclick="closeModalOnBackdrop(event, 'createUserModal')">
        <div class="modal-panel">
            <div class="toolbar">
                <div class="panel-title">
                    <h2>新增用户</h2>
                    <span class="eyebrow">Users</span>
                </div>
                <button type="button" class="modal-close" onclick="closeModal('createUserModal')">关闭</button>
            </div>
            <form action="/admin/users" method="post">
                <label>用户名</label>
                <input name="username" required>
                <label>密码</label>
                <input name="password" type="password" required>
                <label>角色</label>
                <select name="is_admin">
                    <option value="0">普通用户</option>
                    <option value="1">管理员</option>
                </select>
                <button type="submit">创建用户</button>
            </form>
        </div>
    </div>
    """

    jobs_section = f"""
    <div class="card">
        <div class="panel-title">
            <h2>任务管理</h2>
            <span class="eyebrow">Jobs</span>
        </div>
        <div class="table-wrap">
            <table><thead><tr><th>任务ID</th><th>提交人</th><th>状态</th><th>创建时间</th><th>完成时间</th><th>操作</th></tr></thead><tbody>{job_rows or '<tr><td colspan="6">暂无任务</td></tr>'}</tbody></table>
        </div>
    </div>
    """

    reports_section = f"""
    <div class="stack">
        <div class="card">
            <div class="panel-title">
                <h2>服务器累计 Word 报告</h2>
                <span class="eyebrow">Word Files</span>
            </div>
            {report_breadcrumb}
            <div class="table-wrap">
                <table><thead><tr><th>日期</th><th>文档数</th><th>操作</th></tr></thead><tbody>{report_date_rows or '<tr><td colspan="3">暂无 Word 报告</td></tr>'}</tbody></table>
            </div>
        </div>
        <div class="card">
            <div class="panel-title">
                <h2>日期下的用户</h2>
                <span class="eyebrow">{selected_report_date or '请选择日期'}</span>
            </div>
            <div class="table-wrap">
                <table><thead><tr><th>用户</th><th>文档数</th><th>操作</th></tr></thead><tbody>{report_user_rows or '<tr><td colspan="3">请选择日期后查看用户</td></tr>'}</tbody></table>
            </div>
        </div>
        <div class="card">
            <div class="panel-title">
                <h2>用户生成的文档</h2>
                <span class="eyebrow">{selected_report_user or '请选择用户'}</span>
            </div>
            <div class="table-wrap">
                <table><thead><tr><th>任务ID</th><th>文件名</th><th>大小</th><th>更新时间</th><th>操作</th></tr></thead><tbody>{report_doc_rows or '<tr><td colspan="5">请选择日期和用户后查看文档</td></tr>'}</tbody></table>
            </div>
        </div>
    </div>
    """

    audits_section = f"""
    <div class="card">
        <div class="panel-title">
            <h2>最近审计日志</h2>
            <span class="eyebrow">Audit</span>
        </div>
        {audit_pagination}
        <div class="table-wrap">
            <table><thead><tr><th>时间</th><th>用户</th><th>动作</th><th>详情</th></tr></thead><tbody>{audit_rows or '<tr><td colspan="4">暂无审计日志</td></tr>'}</tbody></table>
        </div>
    </div>
    """

    section_body = {
        "users": users_section,
        "jobs": jobs_section,
        "reports": reports_section,
        "audits": audits_section,
    }[admin_section]
    return render_admin_page(user, section_nav, section_body)


@app.post("/admin/announcement")
async def update_announcement(request: Request, content: str = Form(...)) -> Response:
    user = require_admin(request)
    conn = db_connect()
    with conn:
        conn.execute(
            "UPDATE announcements SET content = ?, updated_at = ?, updated_by = ? WHERE id = 1",
            (content, now_local().isoformat(), user["username"]),
        )
    conn.close()
    record_audit(user["id"], "announcement_updated", "更新系统公告", request)
    return RedirectResponse("/admin", status_code=302)


@app.post("/admin/users")
async def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    is_admin: int = Form(0),
) -> Response:
    user = require_admin(request)
    if get_user_by_username(username):
        raise HTTPException(status_code=400, detail="用户名已存在")
    conn = db_connect()
    with conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at) VALUES (?, ?, ?, ?)",
            (username, hash_password(password), int(bool(is_admin)), now_local().isoformat()),
        )
    conn.close()
    record_audit(user["id"], "user_created", f"创建用户 {username}", request)
    return RedirectResponse("/admin", status_code=302)


@app.post("/admin/users/{target_user_id}/password")
async def reset_user_password(
    request: Request,
    target_user_id: int,
    new_password: str = Form(...),
) -> Response:
    admin = require_admin(request)
    new_password = new_password.strip()
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
    return RedirectResponse("/admin", status_code=302)


@app.post("/admin/jobs/{job_id}/delete")
async def admin_delete_job(request: Request, job_id: str) -> Response:
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
    return RedirectResponse(request.headers.get("referer") or "/admin", status_code=302)


def resolve_admin_report_path(job_id: str, file_name: str) -> Path:
    path = (config.report_dir / job_id / Path(file_name).name).resolve()
    if config.report_dir not in path.parents:
        raise HTTPException(status_code=400, detail="非法文件路径")
    if path.suffix.lower() != ".docx":
        raise HTTPException(status_code=400, detail="仅允许管理 Word 报告")
    return path


@app.get("/admin/reports/{job_id}/{file_name}/download")
async def admin_download_report(request: Request, job_id: str, file_name: str) -> FileResponse:
    admin = require_admin(request)
    path = resolve_admin_report_path(job_id, file_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="报告文件不存在")
    record_audit(admin["id"], "report_download", f"管理员下载报告 {path.name}", request)
    return FileResponse(path, filename=path.name)


@app.post("/admin/reports/{job_id}/{file_name}/delete")
async def admin_delete_report(request: Request, job_id: str, file_name: str) -> Response:
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
    return RedirectResponse("/admin", status_code=302)


@app.get("/me")
async def me(request: Request) -> JSONResponse:
    user = require_user(request)
    return JSONResponse({"id": user["id"], "username": user["username"], "is_admin": bool(user["is_admin"])})


@app.get("/announcements")
async def announcements() -> JSONResponse:
    return JSONResponse({"content": announcement_text()})


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "time": now_local().isoformat()})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> HTMLResponse | JSONResponse:
    wants_json = request.headers.get("accept", "").startswith("application/json") or request.url.path in {"/jobs", "/me", "/announcements", "/health"}
    if wants_json:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    return render_error_page(str(exc.detail))


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=int(os.getenv("PORT", "8080")), reload=False)
