"""巡检系统、版本和发布状态机。"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from backend.config import config, now_local
from backend.db import db_connect
from core.report_service import load_config
from core.inspection_docx import merge_incremental_template, parse_template, shift_table_mappings, validate_snapshot
from backend.email_service import is_valid_email
from backend.config import MAX_EMAIL_RECIPIENTS
from core.vbs_generator import generate_vbs

STATUSES = ("draft", "built", "validating", "validated", "published", "retired")
ALLOWED_TRANSITIONS = {
    "draft": {"built"}, "built": {"validating"}, "validating": {"validated", "built"},
    "validated": {"published", "built"}, "published": {"retired"}, "retired": set(),
}

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _safe_key(value: str) -> str:
    key = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    if not key or len(key) > 64:
        raise HTTPException(400, "系统标识不合法")
    return key

def bootstrap_from_legacy() -> None:
    """首次启动把固定 report.json 导入为草稿，重复启动不会覆盖管理员修改。"""
    configs = load_config(config.config_path)
    conn = db_connect()
    try:
        for key, info in configs.items():
            existing = conn.execute("SELECT id FROM inspection_systems WHERE system_key = ?", (key,)).fetchone()
            if existing:
                continue
            now = now_local().isoformat()
            conn.execute("INSERT INTO inspection_systems (system_key, display_name, created_at, updated_at) VALUES (?, ?, ?, ?)", (key, info.get("display_name", key), now, now))
            system_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            template = config.template_dir / info.get("template", "")
            artifact = config.system_artifact_dir / key / "v1"
            artifact.mkdir(parents=True, exist_ok=True)
            template_copy = artifact / template.name
            if template.is_file(): shutil.copy2(template, template_copy)
            try:
                snapshot = parse_template(template_copy, system_key=key, display_name=info.get("display_name", key))
                for device in snapshot["devices"]:
                    configured_name = info.get("hosts", {}).get(str(device["order"]))
                    if configured_name: device["name"] = configured_name
                snapshot["is_english_name"] = bool(info.get("is_english_name", False))
                validate_snapshot(snapshot)
            except (HTTPException, OSError, ValueError):
                snapshot = _legacy_snapshot(key, info)
            conn.execute("""INSERT INTO inspection_system_versions
                (system_id, version, status, source_mode, config_json, recipients_json, template_path, template_sha256, created_at, updated_at)
                VALUES (?, 1, 'draft', 'create', ?, ?, ?, ?, ?, ?)""", (system_id, json.dumps(snapshot, ensure_ascii=False), json.dumps(info.get("recipients", []), ensure_ascii=False), str(template_copy), sha256_file(template_copy) if template_copy.exists() else None, now, now))
        conn.commit()
    finally:
        conn.close()

def _legacy_snapshot(key: str, info: dict[str, Any]) -> dict[str, Any]:
    command_names = ["display version", "display device", "display interface brief", "display ip interface brief", "display ip routing-table", "display logbuffer"]
    devices = [
        {"order": int(order), "name": name, "ip": "", "driver": "huawei_vrp", "commands": [
            {"command": command, "timeout_seconds": 120, "result_cell": {"table": int(order)-1, "row": 4+index, "column": 2}}
            for index, command in enumerate(command_names)
        ]}
        for order, name in info.get("hosts", {}).items()
    ]
    return {"system_key": key, "display_name": info.get("display_name", key), "template": info.get("template", ""), "driver": "huawei_vrp", "devices": devices, "non_command_rules": []}

def list_systems() -> list[dict[str, Any]]:
    conn = db_connect()
    rows = conn.execute("""SELECT s.*, v.version, v.status, v.validation_json
        FROM inspection_systems s
        LEFT JOIN inspection_system_versions v ON v.id = COALESCE(
            s.current_version_id,
            (SELECT latest.id FROM inspection_system_versions latest WHERE latest.system_id=s.id ORDER BY latest.version DESC LIMIT 1)
        )
        ORDER BY s.system_key""").fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_version(version_id: int):
    conn = db_connect(); row = conn.execute("""SELECT v.*, s.system_key, s.display_name, s.current_version_id
        FROM inspection_system_versions v JOIN inspection_systems s ON s.id=v.system_id WHERE v.id=?""", (version_id,)).fetchone(); conn.close()
    return row

def serialize_version(row) -> dict[str, Any]:
    return {
        "id": row["id"], "system_id": row["system_id"], "system_key": row["system_key"],
        "display_name": row["display_name"], "version": row["version"], "status": row["status"],
        "source_mode": row["source_mode"], "config": json.loads(row["config_json"]),
        "recipients": json.loads(row["recipients_json"] or "[]"), "template_sha256": row["template_sha256"],
        "vbs_sha256": row["vbs_sha256"], "validation": json.loads(row["validation_json"] or "{}"),
        "created_at": row["created_at"], "updated_at": row["updated_at"],
        "is_current": row["current_version_id"] == row["id"],
    }

def list_versions(system_id: int) -> list[dict[str, Any]]:
    conn = db_connect(); rows = conn.execute("""SELECT v.*, s.system_key, s.display_name, s.current_version_id
        FROM inspection_system_versions v JOIN inspection_systems s ON s.id=v.system_id
        WHERE v.system_id=? ORDER BY v.version DESC""", (system_id,)).fetchall(); conn.close()
    return [serialize_version(row) for row in rows]

def create_draft(source: Path, *, system_key: str, display_name: str, mode: str, system_id: int | None, user_id: int) -> dict[str, Any]:
    if mode not in {"create", "incremental", "replace"}: raise HTTPException(400, "mode 必须是 create、incremental 或 replace")
    conn = db_connect(); now = now_local().isoformat()
    try:
        if mode == "create":
            key = _safe_key(system_key)
            if conn.execute("SELECT COUNT(*) FROM inspection_systems").fetchone()[0] >= 50: raise HTTPException(409, "巡检系统数量已达到 50 个上限")
            if conn.execute("SELECT 1 FROM inspection_systems WHERE system_key=?", (key,)).fetchone(): raise HTTPException(409, "系统标识已存在")
            conn.execute("INSERT INTO inspection_systems (system_key, display_name, created_at, updated_at) VALUES (?, ?, ?, ?)", (key, display_name.strip() or key, now, now))
            system_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]; version = 1
        else:
            system = conn.execute("SELECT * FROM inspection_systems WHERE id=?", (system_id,)).fetchone()
            if not system: raise HTTPException(404, "系统不存在")
            key = system["system_key"]; display_name = display_name.strip() or system["display_name"]
            version = conn.execute("SELECT COALESCE(MAX(version),0)+1 FROM inspection_system_versions WHERE system_id=?", (system_id,)).fetchone()[0]
        artifact = config.system_artifact_dir / key / f"v{version}"; artifact.mkdir(parents=True, exist_ok=False)
        template = artifact / "template.docx"; shutil.copy2(source, template)
        parsed = parse_template(template, system_key=key, display_name=display_name)
        if mode == "incremental":
            previous = conn.execute("SELECT config_json, template_path FROM inspection_system_versions WHERE system_id=? ORDER BY version DESC LIMIT 1", (system_id,)).fetchone()
            if previous:
                offset = merge_incremental_template(Path(previous["template_path"]), template, template)
                shift_table_mappings(parsed, offset)
                base = json.loads(previous["config_json"]); base["devices"] = [*base.get("devices", []), *parsed["devices"]]
                base["non_command_rules"] = [*base.get("non_command_rules", []), *parsed.get("non_command_rules", [])]
                parsed = validate_snapshot(base)
        parsed = validate_snapshot(parsed)
        conn.execute("""INSERT INTO inspection_system_versions
            (system_id, version, status, source_mode, config_json, recipients_json, template_path, template_sha256, created_by, created_at, updated_at)
            VALUES (?, ?, 'draft', ?, ?, '[]', ?, ?, ?, ?, ?)""", (system_id, version, mode, json.dumps(parsed, ensure_ascii=False), str(template), sha256_file(template), user_id, now, now))
        version_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]; conn.commit()
    except Exception:
        conn.rollback()
        if 'artifact' in locals(): shutil.rmtree(artifact, ignore_errors=True)
        raise
    finally: conn.close()
    return serialize_version(get_version(version_id))

def update_draft(version_id: int, snapshot: dict[str, Any], recipients: list[str]) -> dict[str, Any]:
    row = get_version(version_id)
    if not row: raise HTTPException(404, "版本不存在")
    if row["status"] not in {"draft", "built"}: raise HTTPException(409, "当前状态不可编辑")
    snapshot = validate_snapshot(snapshot)
    if not isinstance(recipients, list) or len(recipients) > MAX_EMAIL_RECIPIENTS or any(not isinstance(item, str) or not is_valid_email(item) for item in recipients): raise HTTPException(400, "收件人白名单格式错误或数量超限")
    conn = db_connect()
    with conn: conn.execute("UPDATE inspection_system_versions SET status='draft', config_json=?, recipients_json=?, vbs_path=NULL, vbs_sha256=NULL, validation_json=NULL, updated_at=? WHERE id=?", (json.dumps(snapshot, ensure_ascii=False), json.dumps(list(dict.fromkeys(recipients)), ensure_ascii=False), now_local().isoformat(), version_id))
    conn.close(); return serialize_version(get_version(version_id))

def build_version(version_id: int) -> dict[str, Any]:
    row = get_version(version_id)
    if not row or row["status"] not in {"draft", "built"}: raise HTTPException(409, "只有草稿可以构建")
    snapshot = validate_snapshot(json.loads(row["config_json"])); script, digest = generate_vbs(row["system_key"], row["version"], snapshot)
    vbs_path = Path(row["template_path"]).parent / "inspection.vbs"; vbs_path.write_text(script, encoding="utf-8-sig", newline="")
    conn = db_connect()
    with conn: conn.execute("UPDATE inspection_system_versions SET status='built', config_json=?, vbs_path=?, vbs_sha256=?, validation_json=NULL, updated_at=? WHERE id=?", (json.dumps(snapshot, ensure_ascii=False), str(vbs_path), digest, now_local().isoformat(), version_id))
    conn.close(); return serialize_version(get_version(version_id))

def delete_draft(version_id: int) -> None:
    row = get_version(version_id)
    if not row: raise HTTPException(404, "版本不存在")
    if row["status"] != "draft": raise HTTPException(409, "只有草稿可以删除")
    conn = db_connect()
    if conn.execute("SELECT 1 FROM jobs WHERE locked_versions LIKE ? LIMIT 1", (f'%"version_id": {version_id}%',)).fetchone(): conn.close(); raise HTTPException(409, "版本已被任务引用")
    with conn: conn.execute("DELETE FROM inspection_system_versions WHERE id=?", (version_id,))
    remaining = conn.execute("SELECT COUNT(*) FROM inspection_system_versions WHERE system_id=?", (row["system_id"],)).fetchone()[0]
    if not remaining:
        with conn: conn.execute("DELETE FROM inspection_systems WHERE id=?", (row["system_id"],))
    conn.close(); shutil.rmtree(Path(row["template_path"]).parent, ignore_errors=True)

def transition(version_id: int, target: str) -> None:
    row = get_version(version_id)
    if not row: raise HTTPException(404, "版本不存在")
    if target not in ALLOWED_TRANSITIONS.get(row["status"], set()): raise HTTPException(409, f"不允许从 {row['status']} 进入 {target}")
    conn = db_connect()
    with conn: conn.execute("UPDATE inspection_system_versions SET status=?, updated_at=? WHERE id=?", (target, now_local().isoformat(), version_id))
    conn.close()

def publish(version_id: int) -> None:
    row = get_version(version_id)
    if not row or row["status"] != "validated": raise HTTPException(409, "只有已验证版本可以发布")
    conn = db_connect(); now = now_local().isoformat()
    with conn:
        conn.execute("UPDATE inspection_system_versions SET status='retired', updated_at=? WHERE system_id=? AND status='published'", (now, row["system_id"]))
        conn.execute("UPDATE inspection_system_versions SET status='published', updated_at=? WHERE id=?", (now, version_id))
        conn.execute("UPDATE inspection_systems SET current_version_id=?, updated_at=? WHERE id=?", (version_id, now, row["system_id"]))
    conn.close()

def activate(version_id: int) -> None:
    row = get_version(version_id)
    if not row or row["status"] not in {"published", "retired"}: raise HTTPException(409, "只能回滚到已发布或已退役版本")
    conn = db_connect(); now = now_local().isoformat()
    with conn:
        conn.execute("UPDATE inspection_system_versions SET status='retired', updated_at=? WHERE system_id=? AND status='published'", (now, row["system_id"]))
        conn.execute("UPDATE inspection_system_versions SET status='published', updated_at=? WHERE id=?", (now, version_id))
        conn.execute("UPDATE inspection_systems SET current_version_id=?, updated_at=? WHERE id=?", (version_id, now, row["system_id"]))
    conn.close()
