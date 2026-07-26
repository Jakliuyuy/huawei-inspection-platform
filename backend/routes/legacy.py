"""SPA 之前的旧入口，仅做 302 跳转。

前端已是挂在 /app/ 下的 SPA，全仓无任何代码引用这些路径，它们只为
老书签兜底。Phase 6 计划删除，只保留 GET /。
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

from backend.audit import record_audit
from backend.auth import clear_session, clear_session_response, get_user_by_session
from backend.config import SESSION_COOKIE

router = APIRouter()


def spa_redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=302)


@router.get("/")
async def home(request: Request) -> RedirectResponse:
    user = get_user_by_session(request.cookies.get(SESSION_COOKIE))
    return spa_redirect("/app/dashboard" if user else "/app/login")


@router.get("/login")
async def login_page() -> RedirectResponse:
    return spa_redirect("/app/login")


@router.post("/login")
async def legacy_login_redirect() -> RedirectResponse:
    return spa_redirect("/app/login")


@router.get("/logout")
async def logout_page() -> RedirectResponse:
    return spa_redirect("/app/login")


@router.post("/logout")
async def legacy_logout_redirect(request: Request) -> Response:
    token = request.cookies.get(SESSION_COOKIE)
    user = get_user_by_session(token)
    if user:
        record_audit(user["id"], "logout", "用户退出登录", request)
    clear_session(token)
    return clear_session_response(spa_redirect("/app/login"))


@router.get("/dashboard")
async def dashboard_redirect() -> RedirectResponse:
    return spa_redirect("/app/dashboard")


@router.get("/upload")
async def upload_redirect() -> RedirectResponse:
    return spa_redirect("/app/tasks/new")


@router.get("/jobs/{job_id}")
async def job_detail_redirect(job_id: str) -> RedirectResponse:
    return spa_redirect(f"/app/tasks/{job_id}")


@router.get("/admin")
async def admin_redirect() -> RedirectResponse:
    return spa_redirect("/app/admin")
