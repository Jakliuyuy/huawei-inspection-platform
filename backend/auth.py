"""用户查询、会话生命周期、登录限流与鉴权守卫。"""

from __future__ import annotations

import sqlite3
from datetime import timedelta

from fastapi import HTTPException, Request, Response

from backend.config import (
    LOGIN_MAX_FAILURES,
    LOGIN_WINDOW_SECONDS,
    SESSION_COOKIE,
    config,
    now_local,
)
from backend.db import db_connect
from backend.security import hash_token, new_session_token

# 登录失败计数，键是 (ip, username)。进程内状态，多 worker 下各自独立。
login_attempts: dict[tuple[str, str], list[float]] = {}


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
    token = new_session_token()
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


def should_rate_limit(key: tuple[str, str]) -> bool:
    now_ts = now_local().timestamp()
    attempts = [ts for ts in login_attempts.get(key, []) if now_ts - ts < LOGIN_WINDOW_SECONDS]
    login_attempts[key] = attempts
    return len(attempts) >= LOGIN_MAX_FAILURES


def note_login_failure(key: tuple[str, str]) -> None:
    login_attempts.setdefault(key, []).append(now_local().timestamp())


def clear_login_failures(key: tuple[str, str]) -> None:
    login_attempts.pop(key, None)


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
