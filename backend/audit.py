"""操作审计。"""

from __future__ import annotations

from fastapi import Request

from backend.config import now_local
from backend.db import db_connect
from backend.security import client_ip


def record_audit(user_id: int | None, action: str, detail: str, request: Request | None = None) -> None:
    ip = client_ip(request)
    conn = db_connect()
    with conn:
        conn.execute(
            "INSERT INTO audit_logs (user_id, action, detail, ip_address, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, action, detail, ip, now_local().isoformat()),
        )
    conn.close()
