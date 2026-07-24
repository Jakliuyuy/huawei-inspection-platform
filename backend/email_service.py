from __future__ import annotations

import json
import os
import smtplib
import ssl
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path
from typing import Optional


def _load_config(config_path: Path) -> dict:
    if config_path.is_file():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_email_recipient_config(config_path: Path) -> dict[str, list[str]]:
    systems = _load_config(config_path)
    result: dict[str, list[str]] = {}
    for sys_key, sys_info in systems.items():
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
        if sys_key.upper() in name_upper:
            return config.get(sys_key, {}).get("recipients", [])
        display_name = config.get(sys_key, {}).get("display_name", "")
        if display_name and display_name[:6] in file_name:
            return config.get(sys_key, {}).get("recipients", [])
    return []


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
) -> None:
    msg = MIMEMultipart()
    msg["From"] = formataddr((from_name, username))
    msg["To"] = ", ".join(to_addrs)
    msg["Subject"] = Header(subject, "utf-8")
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if attachments:
        for filename, content in attachments:
            part = MIMEApplication(content, Name=filename)
            part["Content-Disposition"] = f'attachment; filename="{filename}"'
            msg.attach(part)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
        server.login(username, password)
        server.sendmail(username, to_addrs, msg.as_string())
