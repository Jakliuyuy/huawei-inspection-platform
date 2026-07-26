"""任务列表、创建、详情与下载。"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from backend import upload_sessions
from backend.audit import record_audit
from backend.auth import require_user
from backend.config import API_PREFIX, config, now_local
from backend.payloads import read_json
from backend.db import cleanup_expired_data, db_connect
from backend.downloads import build_download_response
from backend.jobs import enqueue_job, update_job
from backend.pagination import build as build_page
from backend.pagination import normalize as normalize_page
from backend.paths import resolve_within
from backend.queries import ensure_job_access, generate_job_id, get_job, list_jobs_page
from backend.serializers import serialize_job
from core.report_service import load_config

router = APIRouter(prefix=API_PREFIX)


@router.get("/jobs")
async def api_jobs(request: Request, page: int = 1, page_size: int = 12) -> JSONResponse:
    user = require_user(request)
    safe_page, safe_page_size = normalize_page(page, page_size)
    rows, total, stats = list_jobs_page(user, safe_page, safe_page_size)
    return JSONResponse(
        build_page(
            [serialize_job(row) for row in rows],
            safe_page,
            safe_page_size,
            total,
            stats=stats,
        )
    )


@router.post("/jobs")
async def api_create_job(request: Request) -> JSONResponse:
    """由一个已解析的上传会话创建任务。

    上传本身走 POST /uploads；这里只消费 upload_id，并接受用户在预览界面
    选定的系统与报告日期。
    """
    user = require_user(request)
    cleanup_expired_data()

    payload = await read_json(request)
    upload_id = str(payload.get("upload_id", "")).strip()
    if not upload_id:
        raise HTTPException(status_code=400, detail="缺少 upload_id")

    session = upload_sessions.get(upload_id, user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="上传记录不存在")
    if upload_sessions.is_expired(session):
        raise HTTPException(status_code=410, detail="上传记录已过期，请重新上传")

    configs = load_config(config.config_path)
    raw_systems = payload.get("systems", [])
    if not isinstance(raw_systems, list):
        raise HTTPException(status_code=400, detail="systems 必须是数组")
    systems = [str(item) for item in raw_systems]
    unknown = sorted(set(systems) - set(configs))
    if unknown:
        raise HTTPException(status_code=400, detail=f"未知的系统: {', '.join(unknown)}")

    report_date = str(payload.get("report_date", "")).strip()
    if report_date:
        try:
            datetime.strptime(report_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="报告日期格式应为 YYYY-MM-DD") from None
    else:
        report_date = json.loads(session["preview_json"]).get("suggested_report_date") or now_local().strftime("%Y-%m-%d")

    conn = db_connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        job_id = generate_job_id(conn)
        if (config.upload_dir / job_id).exists():
            raise HTTPException(status_code=503, detail="当前任务创建繁忙，请稍后重试")
        conn.execute(
            """
            INSERT INTO jobs (id, user_id, status, progress, status_detail, input_path,
                              created_at, generated_files, report_date, selected_systems)
            VALUES (?, ?, 'queued', 0, '等待工作线程处理', ?, ?, '[]', ?, ?)
            """,
            (
                job_id,
                user["id"],
                "",
                now_local().isoformat(),
                report_date,
                json.dumps(systems, ensure_ascii=False),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    try:
        input_path = upload_sessions.promote(upload_id, job_id)
    except Exception:
        conn = db_connect()
        try:
            with conn:
                conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        finally:
            conn.close()
        shutil.rmtree(config.upload_dir / job_id, ignore_errors=True)
        raise

    update_job(job_id, input_path=str(input_path))
    scope = "全部系统" if not systems else "、".join(systems)
    record_audit(user["id"], "job_created", f"创建任务 {job_id}（{report_date}，{scope}）", request)
    enqueue_job(job_id, user["id"])
    return JSONResponse({"ok": True, "job_id": job_id})


@router.get("/jobs/{job_id}")
async def api_job_detail(request: Request, job_id: str) -> JSONResponse:
    user = require_user(request)
    job = ensure_job_access(get_job(job_id), user)
    return JSONResponse(serialize_job(job))


@router.get("/jobs/{job_id}/download")
async def api_download_job(request: Request, job_id: str) -> Response:
    user = require_user(request)
    job = ensure_job_access(get_job(job_id), user)
    if not job["bundle_path"]:
        raise HTTPException(status_code=404, detail="任务结果尚未生成")
    path = Path(job["bundle_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="结果文件不存在")
    record_audit(user["id"], "download_bundle", f"下载任务 {job_id} 结果", request)
    return build_download_response(request, path, path.name)


@router.get("/jobs/{job_id}/files/{file_name}")
async def api_download_job_file(request: Request, job_id: str, file_name: str) -> Response:
    user = require_user(request)
    job = ensure_job_access(get_job(job_id), user)
    if not job["output_path"]:
        raise HTTPException(status_code=404, detail="任务结果尚未生成")
    path = resolve_within(Path(job["output_path"]), file_name)
    if path is None:
        raise HTTPException(status_code=400, detail="非法文件路径")
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    record_audit(user["id"], "download_file", f"下载任务 {job_id} 文件 {file_name}", request)
    return build_download_response(request, path, file_name)
