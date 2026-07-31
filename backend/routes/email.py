"""报告邮件发送。

两道安全约束在这里汇合，改动时务必保留：
  1. 附件路径必须来自 generated_files 白名单（resolve_job_report_path）
  2. 收件人必须是 config/report.json 白名单的子集，否则 403
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.audit import record_audit
from backend.auth import require_user
from backend.config import (
    API_PREFIX,
    MAX_EMAIL_FILES,
    MAX_EMAIL_RECIPIENTS,
    SMTP_FROM_NAME,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USERNAME,
)
from backend.payloads import read_json
from backend.email_service import is_valid_email, send_emails
from backend.mail import build_email_subject, suggested_recipients_for_file
from backend.paths import job_report_names, resolve_job_report_path
from backend.queries import ensure_job_access, get_job
import json

router = APIRouter(prefix=API_PREFIX)


def _job_recipients(job, file_name: str) -> list[str]:
    locked = json.loads(job["locked_versions"]) if job["locked_versions"] else []
    for item in locked:
        if file_name.startswith(item["system_key"]) or file_name.startswith(item["display_name"]):
            return [address for address in item.get("recipients", []) if is_valid_email(address)]
    return suggested_recipients_for_file(file_name)


@router.get("/jobs/{job_id}/email-suggestions")
async def api_job_email_suggestions(request: Request, job_id: str) -> JSONResponse:
    user = require_user(request)
    job = ensure_job_access(get_job(job_id), user)
    suggestions = [
        {"name": name, "recipients": _job_recipients(job, name)}
        for name in job_report_names(job)
    ]
    return JSONResponse({"suggestions": suggestions})


@router.post("/jobs/{job_id}/send-email")
async def api_send_email(request: Request, job_id: str) -> JSONResponse:
    user = require_user(request)
    job = ensure_job_access(get_job(job_id), user)
    if not job["output_path"]:
        raise HTTPException(status_code=400, detail="任务尚未生成报告文件")
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        raise HTTPException(status_code=400, detail="邮件服务未配置，请联系管理员设置 SMTP_USERNAME 和 SMTP_PASSWORD")

    payload = await read_json(request)
    files_to_send = payload.get("files", [])
    if not isinstance(files_to_send, list) or not files_to_send:
        raise HTTPException(status_code=400, detail="没有指定要发送的文件")
    if len(files_to_send) > MAX_EMAIL_FILES:
        raise HTTPException(status_code=400, detail=f"单次最多发送 {MAX_EMAIL_FILES} 个文件")

    groups: dict[str, dict] = {}

    for entry in files_to_send:
        if not isinstance(entry, dict):
            continue
        file_name = str(entry.get("name", ""))
        raw_recipients = entry.get("recipients", [])
        if not file_name or not isinstance(raw_recipients, list) or not raw_recipients:
            continue
        path = resolve_job_report_path(job, file_name)
        recipients = list(dict.fromkeys(str(addr).strip() for addr in raw_recipients))
        if len(recipients) > MAX_EMAIL_RECIPIENTS:
            raise HTTPException(status_code=400, detail=f"单个文件最多指定 {MAX_EMAIL_RECIPIENTS} 个收件人")
        allowed = set(_job_recipients(job, path.name))
        for addr in recipients:
            if not is_valid_email(addr):
                raise HTTPException(status_code=400, detail=f"收件人地址 {addr} 格式不合法")
            if addr not in allowed:
                raise HTTPException(status_code=403, detail=f"收件人 {addr} 不在 {path.name} 的允许范围内")
        key = ",".join(sorted(recipients))
        if key not in groups:
            groups[key] = {"recipients": recipients, "paths": []}
        groups[key]["paths"].append(path)

    results: list[dict] = []
    errors: list[dict] = []

    def deliver() -> None:
        messages: list[dict[str, Any]] = []
        for group in groups.values():
            all_attachments: list[tuple[str, bytes]] = []
            attached_names: list[str] = []
            for file_path in group["paths"]:
                if not file_path.exists():
                    errors.append({"name": file_path.name, "error": "文件不存在"})
                    continue
                with open(file_path, "rb") as f:
                    all_attachments.append((file_path.name, f.read()))
                attached_names.append(file_path.name)

            if not all_attachments:
                continue

            messages.append(
                {
                    "to_addrs": group["recipients"],
                    "subject": build_email_subject(attached_names),
                    "body": f"您好，\n\n附件为本次生成的巡检报告，共 {len(all_attachments)} 个文件。\n\n此邮件由华为巡检云平台自动发送。",
                    "attachments": all_attachments,
                    "names": attached_names,
                }
            )

        if not messages:
            return

        try:
            outcomes = send_emails(
                smtp_host=SMTP_HOST,
                smtp_port=SMTP_PORT,
                username=SMTP_USERNAME,
                password=SMTP_PASSWORD,
                from_name=SMTP_FROM_NAME,
                messages=messages,
            )
        except Exception as exc:
            for message in messages:
                errors.append({"name": "/".join(message["names"]), "error": str(exc)})
            return

        for message, outcome in zip(messages, outcomes):
            if outcome.get("ok"):
                results.append({"files": message["names"], "recipients": message["to_addrs"]})
                continue
            refused = outcome.get("refused") or []
            detail = outcome.get("error") or f"收件人被拒收: {', '.join(refused)}"
            errors.append({"name": "/".join(message["names"]), "error": detail})

    await run_in_threadpool(deliver)

    sent_detail = "; ".join(
        f"{'/'.join(item['files'])} -> {', '.join(item['recipients'])}" for item in results
    ) or "无"
    failed_detail = "; ".join(f"{item['name']}: {item['error']}" for item in errors) or "无"
    record_audit(
        user["id"],
        "send_email",
        f"任务 {job_id} 发送邮件: 成功 {len(results)} 封，失败 {len(errors)} 个；成功明细 {sent_detail}；失败明细 {failed_detail}",
        request,
    )

    if errors and not results:
        error_detail = "; ".join(f"{e['name']}: {e['error']}" for e in errors)
        raise HTTPException(status_code=500, detail=error_detail)

    return JSONResponse({"ok": len(errors) == 0, "sent": results, "errors": errors})
