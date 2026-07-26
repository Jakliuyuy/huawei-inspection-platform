"""登录、登出、当前用户。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.audit import record_audit
from backend.auth import (
    clear_login_failures,
    clear_session,
    clear_session_response,
    create_session,
    get_user_by_session,
    get_user_by_username,
    issue_session_response,
    note_login_failure,
    require_user,
    should_rate_limit,
)
from backend.config import API_PREFIX, SESSION_COOKIE, config
from backend.security import client_ip, verify_password
from backend.serializers import serialize_user

router = APIRouter(prefix=API_PREFIX)
from backend.payloads import read_json


@router.post("/auth/login")
async def api_login(request: Request) -> JSONResponse:
    if config.local_mode:
        # 本地模式无需登录，老书签打到这里时返回当前用户即可
        return JSONResponse({"ok": True, "user": serialize_user(require_user(request))})
    payload = await read_json(request)
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    attempt_key = (client_ip(request) or "unknown", username)
    if should_rate_limit(attempt_key):
        raise HTTPException(status_code=429, detail="登录失败次数过多，请稍后再试")
    user = get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        note_login_failure(attempt_key)
        record_audit(None, "login_failed", f"用户名 {username} 登录失败", request)
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    clear_login_failures(attempt_key)
    token = create_session(user["id"])
    record_audit(user["id"], "login", "用户登录成功", request)
    response = JSONResponse({"ok": True, "user": serialize_user(user)})
    return issue_session_response(response, token)


@router.post("/auth/logout")
async def api_logout(request: Request) -> JSONResponse:
    if config.local_mode:
        return JSONResponse({"ok": True})
    token = request.cookies.get(SESSION_COOKIE)
    user = get_user_by_session(token)
    if user:
        record_audit(user["id"], "logout", "用户退出登录", request)
    clear_session(token)
    response = JSONResponse({"ok": True})
    return clear_session_response(response)


@router.get("/auth/me")
async def api_me(request: Request) -> JSONResponse:
    user = require_user(request)
    # 前端据此隐藏登录/登出入口
    return JSONResponse({**serialize_user(user), "auth_mode": "local" if config.local_mode else "session"})
