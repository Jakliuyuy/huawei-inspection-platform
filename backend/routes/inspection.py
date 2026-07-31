"""动态巡检系统版本与日志批次 API。"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse

from backend.audit import record_audit
from backend.auth import require_admin, require_user
from backend.config import API_PREFIX, MAX_UPLOAD_BYTES, now_local
from backend.db import db_connect
from backend.downloads import build_download_response
from backend import inspection_systems as systems
from backend import log_batches
from backend.payloads import read_json
from backend.uploads import extract_zip_safe, sanitize_member_name

router = APIRouter(prefix=API_PREFIX)

@router.get("/inspection-systems")
async def list_available_inspection_systems(request: Request) -> JSONResponse:
    require_user(request); conn=db_connect(); rows=conn.execute("""SELECT s.id, s.system_key, s.display_name, v.id AS version_id, v.version
        FROM inspection_systems s JOIN inspection_system_versions v ON v.id=s.current_version_id
        WHERE v.status='published' ORDER BY s.system_key""").fetchall(); conn.close()
    return JSONResponse({"systems":[dict(row) for row in rows]})

@router.get("/admin/inspection-systems")
async def list_inspection_systems(request: Request) -> JSONResponse:
    require_admin(request); return JSONResponse({"systems": systems.list_systems()})

@router.get("/admin/inspection-systems/{system_id}/versions")
async def list_inspection_versions(request: Request, system_id: int) -> JSONResponse:
    require_admin(request); return JSONResponse({"versions": systems.list_versions(system_id)})

@router.get("/admin/system-drafts/{version_id}")
async def get_draft(request: Request, version_id: int) -> JSONResponse:
    require_admin(request); row=systems.get_version(version_id)
    if not row: raise HTTPException(404,"版本不存在")
    return JSONResponse(systems.serialize_version(row))

@router.post("/admin/system-drafts")
async def create_system_draft(request: Request, file: UploadFile=File(...), mode: str=Form("create"), system_key: str=Form(""), display_name: str=Form(""), system_id: int|None=Form(None)) -> JSONResponse:
    admin=require_admin(request)
    if not file.filename or Path(file.filename).suffix.lower() != ".docx": raise HTTPException(400,"仅支持 .docx")
    staging=systems.config.system_artifact_dir / "_uploads"; staging.mkdir(parents=True,exist_ok=True); source=staging/f"{now_local().timestamp()}-{Path(file.filename).name}"; size=0
    try:
        with source.open("wb") as handle:
            while chunk := file.file.read(1024*1024):
                size+=len(chunk)
                if size>MAX_UPLOAD_BYTES: raise HTTPException(400,"DOCX 文件超出上传限制")
                handle.write(chunk)
        result=systems.create_draft(source,system_key=system_key,display_name=display_name,mode=mode,system_id=system_id,user_id=admin["id"])
    finally: source.unlink(missing_ok=True)
    record_audit(admin["id"],"system_draft_created",f"创建 {result['system_key']} v{result['version']} 草稿",request)
    return JSONResponse(result)

@router.put("/admin/system-drafts/{version_id}")
async def update_system_draft(request: Request, version_id: int) -> JSONResponse:
    admin=require_admin(request); payload=await read_json(request); result=systems.update_draft(version_id,payload.get("config",{}),payload.get("recipients",[])); record_audit(admin["id"],"system_draft_updated",f"更新 {result['system_key']} v{result['version']}",request); return JSONResponse(result)

@router.post("/admin/system-drafts/{version_id}/build")
async def build_system_draft(request: Request, version_id: int) -> JSONResponse:
    admin=require_admin(request); result=systems.build_version(version_id); record_audit(admin["id"],"system_version_built",f"构建 {result['system_key']} v{result['version']}",request); return JSONResponse(result)

@router.get("/admin/system-drafts/{version_id}/files/{kind}")
async def download_draft_file(request: Request, version_id: int, kind: str) -> Response:
    admin=require_admin(request); row=systems.get_version(version_id)
    if not row: raise HTTPException(404,"版本不存在")
    path=Path(row["vbs_path"] if kind=="vbs" else row["template_path"] if kind=="docx" else "")
    if not path.is_file(): raise HTTPException(404,"文件尚未生成")
    record_audit(admin["id"],"system_artifact_download",f"下载 {row['system_key']} v{row['version']} {kind}",request); return build_download_response(request,path,f"{row['system_key']}-v{row['version']}.{kind}")

@router.post("/admin/system-drafts/{version_id}/validation-files")
async def validate_system_draft(request: Request, version_id: int, files: list[UploadFile]=File(...)) -> JSONResponse:
    admin=require_admin(request); row=systems.get_version(version_id)
    if not row or row["status"] != "built": raise HTTPException(409,"只有已构建版本可以验证")
    systems.transition(version_id,"validating"); root=Path(row["template_path"]).parent/"validation"; shutil.rmtree(root,ignore_errors=True); root.mkdir()
    try:
        total_size=0
        for upload in files:
            name=sanitize_member_name(upload.filename or ""); target=root/Path(name).name
            with target.open("wb") as handle:
                while chunk := upload.file.read(1024*1024):
                    total_size += len(chunk)
                    if total_size > MAX_UPLOAD_BYTES: raise HTTPException(400,"验证文件总大小超出限制")
                    handle.write(chunk)
            if target.suffix.lower()==".zip": extract_zip_safe(target,root); target.unlink()
        report, _=log_batches.validate(root,systems.get_version(version_id))
        conn=db_connect()
        with conn: conn.execute("UPDATE inspection_system_versions SET status=?, validation_json=?, updated_at=? WHERE id=?",("validated" if report["valid"] else "built",json.dumps(report,ensure_ascii=False),now_local().isoformat(),version_id))
        conn.close()
    except Exception:
        conn=db_connect()
        with conn: conn.execute("UPDATE inspection_system_versions SET status='built', updated_at=? WHERE id=?",(now_local().isoformat(),version_id))
        conn.close(); raise
    record_audit(admin["id"],"system_version_validated",f"验证 {row['system_key']} v{row['version']}: {report['valid']}",request)
    return JSONResponse({"status":"validated" if report["valid"] else "built","validation":report})

@router.post("/admin/system-drafts/{version_id}/publish")
async def publish_system_draft(request: Request, version_id: int) -> JSONResponse:
    admin=require_admin(request); systems.publish(version_id); row=systems.get_version(version_id); record_audit(admin["id"],"system_version_published",f"发布 {row['system_key']} v{row['version']}",request); return JSONResponse(systems.serialize_version(row))

@router.delete("/admin/system-drafts/{version_id}")
async def delete_system_draft(request: Request, version_id: int) -> JSONResponse:
    admin=require_admin(request); systems.delete_draft(version_id); record_audit(admin["id"],"system_draft_deleted",f"删除草稿 {version_id}",request); return JSONResponse({"ok":True})

@router.post("/admin/inspection-systems/{system_id}/versions/{version}/activate")
async def activate_version(request: Request, system_id: int, version: int) -> JSONResponse:
    admin=require_admin(request); conn=db_connect(); row=conn.execute("SELECT id FROM inspection_system_versions WHERE system_id=? AND version=?",(system_id,version)).fetchone(); conn.close()
    if not row: raise HTTPException(404,"版本不存在")
    systems.activate(row["id"]); record_audit(admin["id"],"system_version_activated",f"激活系统 {system_id} v{version}",request); return JSONResponse({"ok":True})

@router.post("/log-batches")
async def create_log_batch(request: Request) -> JSONResponse:
    user=require_user(request); payload=await read_json(request); result=log_batches.create(user["id"],int(payload.get("system_version_id",0))); record_audit(user["id"],"log_batch_created",f"创建日志批次 {result['id']}",request); return JSONResponse(result)

@router.post("/log-batches/{batch_id}/files")
async def append_log_batch_files(request: Request,batch_id: str,files: list[UploadFile]=File(...)) -> JSONResponse:
    user=require_user(request); result=log_batches.save_files(batch_id,user["id"],bool(user["is_admin"]),files); record_audit(user["id"],"log_batch_files_added",f"日志批次 {batch_id} 状态 {result['status']}",request); return JSONResponse(result)

@router.get("/log-batches/{batch_id}")
async def get_log_batch(request: Request,batch_id: str) -> JSONResponse:
    user=require_user(request); return JSONResponse(log_batches.get(batch_id,user["id"],bool(user["is_admin"])))
