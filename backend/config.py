"""应用配置与全局常量。

从 server.py 原样搬来，唯一的实质改动是 APP_ROOT 的定位方式：
本模块位于 backend/ 下，所以要 parent.parent 才是应用根目录。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
except ImportError:  # 未安装时 .env 不生效，见 requirements.txt
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(APP_ROOT / ".env")

APP_TITLE = "华为巡检云平台"
SESSION_COOKIE = "inspection_session"
LOCAL_TZ = timezone(timedelta(hours=8))
API_PREFIX = "/api"

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(200 * 1024 * 1024)))
MAX_EXTRACTED_BYTES = int(os.getenv("MAX_EXTRACTED_BYTES", str(1024 * 1024 * 1024)))
MAX_EXTRACTED_FILES = int(os.getenv("MAX_EXTRACTED_FILES", "5000"))

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.139.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "华为巡检云平台")
MAX_EMAIL_FILES = int(os.getenv("MAX_EMAIL_FILES", "20"))
MAX_EMAIL_RECIPIENTS = int(os.getenv("MAX_EMAIL_RECIPIENTS", "20"))

LOGIN_WINDOW_SECONDS = 300
LOGIN_MAX_FAILURES = 5

STATUS_LABELS = {
    "queued": "排队中",
    "running": "处理中",
    "completed": "已完成",
    "failed": "失败",
}
SYSTEM_DIR_NAMES = ("TOC", "TOB", "NM1", "NM2", "NM3", "Softswitch", "SMS", "GPRS", "IntelligentNet")


LOCAL_MODE = os.getenv("LOCAL_MODE", "false").lower() == "true"
LOCAL_USERNAME = os.getenv("LOCAL_USERNAME", "local")


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
    local_mode: bool
    frontend_dir: Path


def build_config() -> AppConfig:
    app_root = APP_ROOT
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
        # 本地走 http，Secure Cookie 会被部分浏览器直接丢弃，表现为
        # 「登录成功但下一个请求就 401」。显式设置优先，否则由是否本地模式决定。
        secure_cookies=(
            os.getenv("SECURE_COOKIES").lower() == "true"
            if os.getenv("SECURE_COOKIES") is not None
            else not LOCAL_MODE
        ),
        local_mode=LOCAL_MODE,
        frontend_dir=Path(os.getenv("FRONTEND_DIR") or app_root / "web" / "dist").resolve(),
    )


config = build_config()


def now_local() -> datetime:
    return datetime.now(tz=LOCAL_TZ)
