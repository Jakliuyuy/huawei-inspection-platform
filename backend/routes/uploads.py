"""上传暂存与解析预览。"""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from backend import upload_sessions
from backend.audit import record_audit
from backend.auth import require_user
from backend.config import API_PREFIX, config
from backend.uploads import save_uploads
from core.report_service import load_config

router = APIRouter(prefix=API_PREFIX)


@router.post("/uploads")
async def api_create_upload(request: Request, files: list[UploadFile] = File(...)) -> JSONResponse:
    user = require_user(request)
    upload_sessions.collect_garbage()
    if not files:
        raise HTTPException(status_code=400, detail="至少上传一个文件")

    upload_id = upload_sessions.new_upload_id()
    session_dir = upload_sessions.staging_root() / upload_id
    if session_dir.exists():
        raise HTTPException(status_code=503, detail="上传繁忙，请稍后重试")
    session_dir.mkdir(parents=True, exist_ok=False)

    try:
        prepared_dir = save_uploads(session_dir, files)
        preview = upload_sessions.analyze(upload_id, prepared_dir)
        upload_sessions.create(user["id"], upload_id, prepared_dir, preview)
    except Exception:
        upload_sessions._remove_session_dir(session_dir / "prepared", upload_id)
        raise

    record_audit(user["id"], "upload_created", f"上传暂存 {upload_id}", request)
    return JSONResponse(preview.to_payload(load_config(config.config_path)))


@router.get("/uploads/{upload_id}")
async def api_get_upload(request: Request, upload_id: str) -> JSONResponse:
    user = require_user(request)
    row = upload_sessions.get(upload_id, user["id"])
    if not row:
        raise HTTPException(status_code=404, detail="上传记录不存在")
    if upload_sessions.is_expired(row):
        raise HTTPException(status_code=410, detail="上传记录已过期，请重新上传")
    import json

    return JSONResponse(json.loads(row["preview_json"]))


@router.delete("/uploads/{upload_id}")
async def api_delete_upload(request: Request, upload_id: str) -> JSONResponse:
    user = require_user(request)
    row = upload_sessions.get(upload_id, user["id"])
    if not row:
        raise HTTPException(status_code=404, detail="上传记录不存在")
    upload_sessions.drop(upload_id)
    return JSONResponse({"ok": True})
