from __future__ import annotations

import json
import os
import re
import smtplib
import ssl
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path
from typing import Any, Optional

SMTP_TIMEOUT_SECONDS = 30
_EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+!#$&'*/=?^`{|}~-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")


def is_valid_email(address: str) -> bool:
    if not isinstance(address, str) or not address or len(address) > 254:
        return False
    if any(ch in address for ch in ("\r", "\n", "\t", " ", ",", ";", "<", ">")):
        return False
    return bool(_EMAIL_PATTERN.match(address))


def _load_config(config_path: Path) -> dict:
    if config_path.is_file():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            return {}
        if isinstance(data, dict):
            return data
    return {}


def get_email_recipient_config(config_path: Path) -> dict[str, list[str]]:
    systems = _load_config(config_path)
    result: dict[str, list[str]] = {}
    for sys_key, sys_info in systems.items():
        if not isinstance(sys_info, dict):
            continue
        recipients = sys_info.get("recipients", [])
        if recipients:
            result[sys_key] = recipients
    return result


def get_system_recipients_for_file(
    config_path: Path,
    file_name: str,
    system_keys: Optional[list[str]] = None,
) -> list[str]:
    if system_keys is None:
        system_keys = ("TOC", "TOB", "GPRS", "SMS", "Softswitch", "IntelligentNet", "NM1", "NM2", "NM3")
    config = _load_config(config_path)
    name_upper = file_name.upper().replace(".DOCX", "").replace(".DOC", "")
    for sys_key in system_keys:
        sys_info = config.get(sys_key, {})
        if not isinstance(sys_info, dict):
            continue
        if sys_key.upper() in name_upper:
            return sys_info.get("recipients", [])
        display_name = sys_info.get("display_name", "")
        if display_name and display_name[:6] in file_name:
            return sys_info.get("recipients", [])
    return []


def _build_message(
    username: str,
    from_name: str,
    to_addrs: list[str],
    subject: str,
    body: str,
    attachments: Optional[list[tuple[str, bytes]]] = None,
) -> MIMEMultipart:
    msg = MIMEMultipart()
    msg["From"] = formataddr((from_name, username))
    msg["To"] = ", ".join(to_addrs)
    msg["Subject"] = Header(subject, "utf-8")
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if attachments:
        for filename, content in attachments:
            part = MIMEApplication(content)
            part.add_header("Content-Disposition", "attachment", filename=("utf-8", "", filename))
            msg.attach(part)
    return msg


def send_email(
    smtp_host: str,
    smtp_port: int,
    username: str,
    password: str,
    from_name: str,
    to_addrs: list[str],
    subject: str,
    body: str,
    attachments: Optional[list[tuple[str, bytes]]] = None,
) -> dict:
    """返回被服务器拒绝的收件人字典，全部投递成功时为空字典。"""
    msg = _build_message(username, from_name, to_addrs, subject, body, attachments)
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=SMTP_TIMEOUT_SECONDS) as server:
        server.login(username, password)
        return server.sendmail(username, to_addrs, msg.as_string())


def send_emails(
    smtp_host: str,
    smtp_port: int,
    username: str,
    password: str,
    from_name: str,
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """一次建连并登录后连续投递多封邮件，按入参顺序返回每封的结果。

    messages 中每项需包含 to_addrs/subject/body，可选 attachments。
    """
    results: list[dict[str, Any]] = []
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=SMTP_TIMEOUT_SECONDS) as server:
        server.login(username, password)
        for message in messages:
            to_addrs = message.get("to_addrs", [])
            try:
                msg = _build_message(
                    username,
                    from_name,
                    to_addrs,
                    message.get("subject", ""),
                    message.get("body", ""),
                    message.get("attachments"),
                )
                refused = server.sendmail(username, to_addrs, msg.as_string())
                results.append({"ok": not refused, "refused": sorted(refused), "error": ""})
            except Exception as exc:
                results.append({"ok": False, "refused": [], "error": str(exc)})
    return results
