"""管理端：用户、任务、报告归档、审计。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from backend.audit import record_audit
from backend.auth import clear_user_sessions, get_user_by_username, require_admin
from backend.config import API_PREFIX, now_local
from backend.payloads import read_json
from backend.db import db_connect
from backend.downloads import build_download_response
from backend.pagination import build as build_page
from backend.pagination import normalize as normalize_page
from backend.paths import resolve_admin_report_path
from backend.persistence import list_admin_users as list_admin_users_impl
from backend.persistence import list_audits_page as list_audits_page_impl
from backend.queries import (
    list_jobs_page,
    list_report_date_stats,
    list_report_files_for_user,
    list_report_user_stats,
)
from backend.security import hash_password
from backend.serializers import serialize_audit, serialize_job, serialize_user
from backend.storage import delete_job_storage

router = APIRouter(prefix=API_PREFIX)


def list_admin_users() -> list[sqlite3.Row]:
    return list_admin_users_impl(db_connect=db_connect)


def list_audits_page(page: int, page_size: int) -> tuple[list[sqlite3.Row], int]:
    return list_audits_page_impl(db_connect=db_connect, page=page, page_size=page_size)


@router.get("/admin/users")
async def api_admin_users(request: Request) -> JSONResponse:
    require_admin(request)
    return JSONResponse([serialize_user(row) for row in list_admin_users()])


@router.post("/admin/users")
async def api_admin_create_user(request: Request) -> JSONResponse:
    admin = require_admin(request)
    payload = await read_json(request)
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


@router.put("/admin/users/{target_user_id}/password")
async def api_admin_reset_password(request: Request, target_user_id: int) -> JSONResponse:
    admin = require_admin(request)
    payload = await read_json(request)
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


@router.put("/admin/announcement")
async def api_update_announcement(request: Request) -> JSONResponse:
    user = require_admin(request)
    payload = await read_json(request)
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


@router.get("/admin/jobs")
async def api_admin_jobs(request: Request, page: int = 1, page_size: int = 20) -> JSONResponse:
    admin = require_admin(request)
    safe_page, safe_page_size = normalize_page(page, page_size)
    rows, total, stats = list_jobs_page(admin, safe_page, safe_page_size)
    return JSONResponse(
        build_page(
            [serialize_job(row) for row in rows],
            safe_page,
            safe_page_size,
            total,
            stats=stats,
        )
    )


@router.delete("/admin/jobs/{job_id}")
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
        conn.execute("DELETE FROM report_files WHERE job_id = ?", (job_id,))
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.close()
    delete_job_storage(job)
    record_audit(admin["id"], "job_deleted", f"管理员删除任务 {job_id}", request)
    return JSONResponse({"ok": True})


@router.get("/admin/reports/dates")
async def api_report_dates(request: Request) -> JSONResponse:
    require_admin(request)
    return JSONResponse(list_report_date_stats())


@router.get("/admin/reports/users")
async def api_report_users(request: Request, date: str) -> JSONResponse:
    require_admin(request)
    return JSONResponse(list_report_user_stats(date))


@router.get("/admin/reports/files")
async def api_report_files(request: Request, date: str, user: str) -> JSONResponse:
    require_admin(request)
    items = [
        {
            **item,
            "download_url": f"{API_PREFIX}/admin/reports/{item['job_id']}/{item['name']}/download",
        }
        for item in list_report_files_for_user(date, user)
    ]
    return JSONResponse(items)


@router.get("/admin/reports/{job_id}/{file_name}/download")
async def api_admin_download_report(request: Request, job_id: str, file_name: str) -> Response:
    admin = require_admin(request)
    path = resolve_admin_report_path(job_id, file_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="报告文件不存在")
    record_audit(admin["id"], "report_download", f"管理员下载报告 {path.name}", request)
    return build_download_response(request, path, path.name)


@router.delete("/admin/reports/{job_id}/{file_name}")
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
            conn.execute("DELETE FROM report_files WHERE job_id = ? AND file_name = ?", (job_id, path.name))
    conn.close()
    parent = path.parent
    if parent.exists() and not any(parent.iterdir()):
        parent.rmdir()
    record_audit(admin["id"], "report_deleted", f"管理员删除报告 {path.name}", request)
    return JSONResponse({"ok": True})


@router.get("/admin/audits")
async def api_admin_audits(request: Request, page: int = 1, page_size: int = 20) -> JSONResponse:
    require_admin(request)
    safe_page, safe_page_size = normalize_page(page, page_size)
    audits, total = list_audits_page(safe_page, safe_page_size)
    return JSONResponse(
        build_page([serialize_audit(item) for item in audits], safe_page, safe_page_size, total)
    )
