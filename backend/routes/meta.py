"""公告、收件人配置、健康检查。"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.auth import require_user
from backend.config import API_PREFIX, config, now_local
from backend.db import db_connect
from backend.email_service import get_email_recipient_config
from backend.queries import announcement_text
from backend.upload_sessions import output_name_template
from core.report_service import load_config

router = APIRouter(prefix=API_PREFIX)


@router.get("/announcements")
async def api_announcements(request: Request) -> JSONResponse:
    require_user(request)
    return JSONResponse({"content": announcement_text()})


@router.get("/email-config")
async def api_email_config(request: Request) -> JSONResponse:
    require_user(request)
    recipients = get_email_recipient_config(config.config_path)
    return JSONResponse(recipients)


@router.get("/systems")
async def api_systems(request: Request) -> JSONResponse:
    """可生成的系统清单（对应旧 CLI 的 --list）。"""
    require_user(request)
    configs = load_config(config.config_path)
    return JSONResponse(
        {
            "systems": [
                {
                    "key": key,
                    "display_name": info.get("display_name", key),
                    "template": info.get("template", ""),
                    "host_count": len(info.get("hosts", {})),
                    "output_name_template": output_name_template(key, info),
                }
                for key, info in configs.items()
            ]
        }
    )


@router.get("/health")
async def api_health() -> JSONResponse:
    conn = db_connect()
    try:
        conn.execute("SELECT 1").fetchone()
    finally:
        conn.close()
    return JSONResponse({"status": "ok", "time": now_local().isoformat()})
