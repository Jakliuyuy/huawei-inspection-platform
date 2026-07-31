"""日志批次落盘、执行清单解析和严格完整度校验。"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import secrets
import shutil
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile

from backend.config import MAX_UPLOAD_BYTES, config, now_local
from backend.db import db_connect
from backend.inspection_systems import get_version
from backend.uploads import extract_zip_safe, sanitize_member_name

MANIFEST_NAME = "inspection-manifest.tsv"
CLI_ERRORS = ("error:", "unknown command", "unrecognized command", "incomplete command", "ambiguous command", "错误：", "命令不存在")

def _sha(path: Path) -> str:
    digest = hashlib.sha256(); digest.update(path.read_bytes()); return digest.hexdigest()

def create(user_id: int, version_id: int) -> dict[str, Any]:
    version = get_version(version_id) if version_id else None
    if version_id and (not version or version["status"] not in {"published", "retired", "validated"}): raise HTTPException(409, "只能为已验证的系统版本创建日志批次")
    batch_id = f"lb-{now_local().strftime('%Y%m%d')}-{secrets.token_hex(4)}"; root = config.log_batch_dir / batch_id; root.mkdir(parents=True)
    now = now_local().isoformat(); conn = db_connect()
    with conn: conn.execute("INSERT INTO log_batches (id,user_id,system_version_id,status,root_path,created_at,updated_at) VALUES (?,?,?,'collecting',?,?,?)", (batch_id,user_id,version_id or None,str(root),now,now))
    conn.close(); return get(batch_id, user_id, False)

def _row(batch_id: str, user_id: int, is_admin: bool):
    conn = db_connect(); row = conn.execute("SELECT * FROM log_batches WHERE id=?" + ("" if is_admin else " AND user_id=?"), (batch_id,) if is_admin else (batch_id,user_id)).fetchone(); conn.close()
    if not row: raise HTTPException(404, "日志批次不存在")
    return row

def save_files(batch_id: str, user_id: int, is_admin: bool, uploads: list[UploadFile]) -> dict[str, Any]:
    batch = _row(batch_id,user_id,is_admin); root=Path(batch["root_path"]); total=0
    for upload in uploads:
        name = sanitize_member_name(upload.filename or ""); suffix=Path(name).suffix.lower()
        if suffix not in {".zip", ".log", ".tsv"}: raise HTTPException(400, f"不支持的文件类型: {name}")
        target = root / Path(name).name
        with target.open("wb") as handle:
            while chunk := upload.file.read(1024*1024):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES: raise HTTPException(400,"上传文件总大小超出限制")
                handle.write(chunk)
        if suffix == ".zip":
            extract_zip_safe(target, root); target.unlink()
    _index_files(batch_id, root)
    version = get_version(batch["system_version_id"]) if batch["system_version_id"] else _infer_version(root)
    if version and not batch["system_version_id"]:
        conn=db_connect()
        with conn: conn.execute("UPDATE log_batches SET system_version_id=? WHERE id=?",(version["id"],batch_id))
        conn.close()
    if version:
        report, manifest = validate(root, version)
    else:
        manifests=list(root.rglob(MANIFEST_NAME)); manifest=[]
        report={"valid":False,"issues":["执行清单未指定现存系统版本"] if manifests else ["等待上传执行清单"],"devices":[]}
    status = "validated" if report["valid"] else ("invalid" if manifest else "collecting")
    conn=db_connect()
    with conn: conn.execute("UPDATE log_batches SET status=?, manifest_json=?, validation_json=?, updated_at=? WHERE id=?", (status,json.dumps(manifest,ensure_ascii=False) if manifest else None,json.dumps(report,ensure_ascii=False),now_local().isoformat(),batch_id))
    conn.close(); return get(batch_id,user_id,is_admin)

def _index_files(batch_id: str, root: Path) -> None:
    conn=db_connect()
    with conn:
        conn.execute("DELETE FROM log_batch_files WHERE batch_id=?",(batch_id,))
        for path in sorted(p for p in root.rglob('*') if p.is_file()):
            rel=path.relative_to(root).as_posix()
            conn.execute("INSERT INTO log_batch_files (batch_id,file_name,file_path,file_size,sha256,created_at) VALUES (?,?,?,?,?,?)",(batch_id,rel,str(path),path.stat().st_size,_sha(path),now_local().isoformat()))
    conn.close()

def _read_text(path: Path) -> str:
    for encoding in ("utf-8-sig","utf-8","gb18030"):
        try: return path.read_text(encoding=encoding)
        except UnicodeDecodeError: continue
    return path.read_text(encoding="utf-8",errors="replace")

def _infer_version(root: Path):
    manifests=list(root.rglob(MANIFEST_NAME))
    if len(manifests)!=1: return None
    try: first=next(csv.DictReader(io.StringIO(_read_text(manifests[0])),delimiter="\t"))
    except (StopIteration,csv.Error): return None
    conn=db_connect(); row=conn.execute("""SELECT v.id FROM inspection_system_versions v JOIN inspection_systems s ON s.id=v.system_id
        WHERE s.system_key=? AND v.version=?""",(first.get("system_key",""),first.get("system_version",""))).fetchone(); conn.close()
    return get_version(row["id"]) if row else None

def validate(root: Path, version) -> tuple[dict[str, Any], list[dict[str,str]]]:
    manifests=list(root.rglob(MANIFEST_NAME)); issues=[]
    if len(manifests)!=1: return {"valid":False,"issues":["必须且只能包含一份 inspection-manifest.tsv"],"devices":[]}, []
    try: rows=list(csv.DictReader(io.StringIO(_read_text(manifests[0])),delimiter="\t"))
    except csv.Error as error: return {"valid":False,"issues":[f"执行清单格式错误: {error}"],"devices":[]}, []
    required={"system_key","system_version","script_sha256","device_name","ip","log_file","command_index","command","timeout_seconds","status"}
    if not rows or not required.issubset(rows[0]): return {"valid":False,"issues":["执行清单缺少必填列或数据行"],"devices":[]}, rows
    snapshot=json.loads(version["config_json"]); expected={d["name"]:d for d in snapshot["devices"]}; seen:dict[str,list[dict[str,str]]]={}
    for row in rows:
        name=row["device_name"].strip(); seen.setdefault(name,[]).append(row)
        if row["system_key"]!=version["system_key"] or row["system_version"]!=str(version["version"]): issues.append(f"{name}: 系统版本不符")
        if row["script_sha256"]!=version["vbs_sha256"]: issues.append(f"{name}: 脚本摘要不符")
    duplicate_rows=[name for name, items in seen.items() if len({item["command_index"] for item in items}) != len(items)]
    if duplicate_rows: issues.append("重复设备/命令记录: "+"、".join(duplicate_rows))
    for name, device in expected.items():
        device_rows=seen.get(name,[])
        if not device_rows: issues.append(f"缺设备: {name}"); continue
        if any(row["ip"] != str(device.get("ip", "")) for row in device_rows): issues.append(f"{name}: IP 不符")
        actual={(int(row["command_index"]),row["command"]):row for row in device_rows if row["command_index"].isdigit()}
        for idx, command in enumerate(device["commands"],1):
            row=actual.get((idx,command["command"]))
            if not row: issues.append(f"{name}: 缺命令 {command['command']}"); continue
            if row["status"] not in {"success","no_data"}: issues.append(f"{name}: {command['command']} 状态为 {row['status']}")
            log_candidates=[p for p in root.rglob(Path(row["log_file"]).name) if p.is_file()]
            if len(log_candidates)!=1: issues.append(f"{name}: 日志文件缺失或重名 {row['log_file']}"); continue
            text=_read_text(log_candidates[0]); lower=text.lower()
            if command["command"].lower() not in lower: issues.append(f"{name}: 日志未记录命令 {command['command']}")
            if any(token in lower for token in CLI_ERRORS): issues.append(f"{name}: 日志包含 CLI 错误")
    extras=sorted(set(seen)-set(expected))
    if extras: issues.append("清单包含未知设备: "+"、".join(extras))
    return {"valid":not issues,"issues":list(dict.fromkeys(issues)),"devices":[{"name":name,"expected_commands":len(d["commands"]),"actual_commands":len(seen.get(name,[])),"complete":bool(seen.get(name))} for name,d in expected.items()]}, rows

def get(batch_id: str, user_id: int, is_admin: bool) -> dict[str, Any]:
    row=_row(batch_id,user_id,is_admin); version=get_version(row["system_version_id"]) if row["system_version_id"] else None
    return {"id":row["id"],"status":row["status"],"system_version_id":row["system_version_id"],"system_key":version["system_key"] if version else "","version":version["version"] if version else None,"validation":json.loads(row["validation_json"] or "{}"),"created_at":row["created_at"],"updated_at":row["updated_at"]}
