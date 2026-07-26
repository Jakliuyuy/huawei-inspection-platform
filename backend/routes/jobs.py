"""任务列表、创建、详情与下载。"""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse

from backend.audit import record_audit
from backend.auth import require_user
from backend.config import API_PREFIX, config, now_local
from backend.db import cleanup_expired_data, db_connect
from backend.downloads import build_download_response
from backend.jobs import enqueue_job, update_job
from backend.pagination import build as build_page
from backend.pagination import normalize as normalize_page
from backend.queries import ensure_job_access, generate_job_id, get_job, list_jobs_page
from backend.serializers import serialize_job
from backend.uploads import save_uploads

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
async def api_create_job(request: Request, files: list[UploadFile] = File(...)) -> JSONResponse:
    user = require_user(request)
    cleanup_expired_data()
    if not files:
        raise HTTPException(status_code=400, detail="至少上传一个文件")
    conn = db_connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        job_id = generate_job_id(conn)
        job_dir = config.upload_dir / job_id
        if job_dir.exists():
            raise HTTPException(status_code=503, detail="当前任务创建繁忙，请稍后重试")
        job_dir.mkdir(parents=True, exist_ok=False)
        conn.execute(
            """
            INSERT INTO jobs (id, user_id, status, progress, status_detail, input_path, created_at, generated_files)
            VALUES (?, ?, 'queued', 0, '等待工作线程处理', ?, ?, '[]')
            """,
            (job_id, user["id"], "", now_local().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
    try:
        input_path = save_uploads(job_dir, files)
    except Exception:
        conn = db_connect()
        try:
            with conn:
                conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        finally:
            conn.close()
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    update_job(job_id, input_path=str(input_path))
    record_audit(user["id"], "job_created", f"创建任务 {job_id}", request)
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
    path = Path(job["output_path"]) / file_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    record_audit(user["id"], "download_file", f"下载任务 {job_id} 文件 {file_name}", request)
    return build_download_response(request, path, file_name)
