"""邮件主题构造与收件人白名单解析。"""

from __future__ import annotations

import re
from pathlib import Path

from backend.config import config
from backend.email_service import get_system_recipients_for_file, is_valid_email

RE_COMPACT_DATE = re.compile(r"(\d{4})(\d{2})(\d{2})")


def _extract_date_str(file_name: str) -> tuple[str, str]:
    m = RE_COMPACT_DATE.search(file_name)
    if m:
        month = str(int(m.group(2)))
        day = str(int(m.group(3)))
        return m.group(0), f"{month}月{day}日"
    return "", ""


def _extract_system_short(file_name: str) -> str:
    if file_name.startswith("TOC"):
        return "TOC"
    if file_name.startswith("TOB"):
        return "TOB"
    if file_name.startswith("GPRS"):
        return "GPRS"
    if "短信" in file_name:
        return "短信"
    if "软交换" in file_name:
        return "软交换"
    if "智能网" in file_name:
        return "智能网"
    if "网管1" in file_name:
        return "网管1"
    if "网管2" in file_name:
        return "网管2"
    if "网管3" in file_name:
        return "网管3"
    return ""


def build_email_subject(file_names: list[str]) -> str:
    stem = Path(file_names[0]).stem
    if len(file_names) == 1:
        return stem

    shorts = [_extract_system_short(name) for name in file_names]
    shorts = [s for s in shorts if s]
    _, date_str = _extract_date_str(file_names[0])

    if shorts:
        joined = "/".join(shorts)
        return f"{joined}网设备巡检报告_{date_str}" if date_str else f"{joined}网设备巡检报告"

    return f"巡检报告 - {'/'.join(file_names)}"


def suggested_recipients_for_file(file_name: str) -> list[str]:
    """该报告允许的收件人集合。

    这同时是发信端点的白名单来源：客户端提交的收件人必须是它的子集，
    否则 403。前端的建议值也来自这里，两侧共用一份配置。
    """
    recipients = get_system_recipients_for_file(config.config_path, file_name)
    return [addr for addr in recipients if is_valid_email(addr)]
