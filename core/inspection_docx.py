"""巡检 DOCX 的离线结构提取与安全检查。"""
from __future__ import annotations

import re
import zipfile
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from docx import Document
from fastapi import HTTPException

IP_RE = re.compile(r"(?<!\d)(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?!\d)")
READ_ONLY_PREFIXES = ("display ", "dis ", "show ")
BLOCKED_WORDS = ("reboot", "restart", "reset", "save", "delete", "undo ", "shutdown", "format", "configure", "system-view", "commit")
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
MAX_DOCX_FILES = 2000
MAX_DOCX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024

def inspect_docx_security(path: Path) -> None:
    if path.suffix.lower() != ".docx" or not zipfile.is_zipfile(path):
        raise HTTPException(400, "仅支持有效的 .docx 文件")
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist(); names = [member.filename for member in members]
        if len(members) > MAX_DOCX_FILES or sum(member.file_size for member in members) > MAX_DOCX_UNCOMPRESSED_BYTES:
            raise HTTPException(400, "DOCX 解压后的大小或文件数超出限制")
        if any(Path(name.replace("\\", "/")).is_absolute() or ".." in Path(name.replace("\\", "/")).parts for name in names):
            raise HTTPException(400, "DOCX 包含非法内部路径")
        if any(name.startswith("word/embeddings/") or name.endswith("vbaProject.bin") for name in names):
            raise HTTPException(400, "DOCX 包含嵌入对象或宏，已拒绝")
        for name in names:
            if not name.endswith(".rels"): continue
            root = ET.fromstring(archive.read(name))
            for rel in root.findall(f"{{{REL_NS}}}Relationship"):
                if rel.attrib.get("TargetMode") == "External":
                    raise HTTPException(400, "DOCX 包含外部关系，已拒绝")

def validate_read_only_command(command: str) -> str:
    normalized = " ".join(command.strip().split())
    lower = normalized.lower()
    if not lower.startswith(READ_ONLY_PREFIXES) or any(word in lower for word in BLOCKED_WORDS):
        raise HTTPException(400, f"命令不是允许的只读命令: {normalized}")
    if any(ch in normalized for ch in ("\r", "\n", ";", "&", "|")):
        raise HTTPException(400, f"命令包含非法控制符: {normalized}")
    return normalized

def parse_template(path: Path, *, system_key: str, display_name: str) -> dict[str, Any]:
    inspect_docx_security(path)
    doc = Document(path)
    devices: list[dict[str, Any]] = []
    non_commands: list[dict[str, Any]] = []
    for table_index, table in enumerate(doc.tables):
        header_text = "\n".join(cell.text for row in table.rows[:3] for cell in row.cells)
        ips = IP_RE.findall(header_text)
        name = _extract_name(header_text)
        commands: list[dict[str, Any]] = []
        for row_index, row in enumerate(table.rows):
            if len(row.cells) < 3: continue
            label = row.cells[1].text.strip()
            if not label: continue
            if label.lower().startswith(READ_ONLY_PREFIXES):
                command = validate_read_only_command(label)
                commands.append({"command": command, "timeout_seconds": 120, "result_cell": {"table": table_index, "row": row_index, "column": 2}})
            elif row_index >= 4:
                non_commands.append({"label": label, "result_cell": {"table": table_index, "row": row_index, "column": 2}, "mode": "preserve", "value": "", "source_command": ""})
        if name or ips or commands:
            devices.append({"order": len(devices) + 1, "name": name or f"设备{len(devices)+1}", "ip": ips[0] if ips else "", "driver": _guess_driver(commands), "commands": commands, "table_index": table_index})
    if not devices: raise HTTPException(400, "未在 DOCX 表格中识别到设备")
    return {"system_key": system_key, "display_name": display_name, "template": path.name, "devices": devices, "non_command_rules": non_commands}

def _extract_name(text: str) -> str:
    for pattern in (r"(?:设备名称|名称|主机名|型号)\s*[:：]\s*([^\n\r]+)", r"<([^<>\s]+)>"):
        match = re.search(pattern, text, re.I)
        if match: return match.group(1).strip()
    return ""

def _guess_driver(commands: list[dict[str, Any]]) -> str:
    return "generic_show" if commands and all(item["command"].lower().startswith("show ") for item in commands) else "huawei_vrp"

def validate_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    devices = snapshot.get("devices")
    if not isinstance(devices, list) or not devices or len(devices) > 100: raise HTTPException(400, "设备数量必须为 1 到 100")
    try: devices.sort(key=lambda item: int(item.get("order", 0)))
    except (TypeError, ValueError): raise HTTPException(400, "设备顺序必须是整数") from None
    names: set[str] = set(); ips: set[str] = set()
    for order, device in enumerate(devices, 1):
        name = str(device.get("name", "")).strip(); ip = str(device.get("ip", "")).strip()
        if not name: raise HTTPException(400, f"第 {order} 台设备名称为空")
        name_key = name.casefold()
        if name_key in names: raise HTTPException(409, f"设备名称冲突: {name}")
        names.add(name_key)
        if ip:
            if not IP_RE.fullmatch(ip): raise HTTPException(400, f"管理 IP 不合法: {ip}")
            if ip in ips: raise HTTPException(409, f"管理 IP 冲突: {ip}")
            ips.add(ip)
        driver = device.get("driver", "huawei_vrp")
        if driver not in {"huawei_vrp", "generic_show"}: raise HTTPException(400, f"未知驱动: {driver}")
        raw_commands = device.get("commands", [])
        if not isinstance(raw_commands, list) or not raw_commands: raise HTTPException(400, f"设备 {name} 没有命令")
        for item in raw_commands:
            item["command"] = validate_read_only_command(str(item.get("command", "")))
            timeout = int(item.get("timeout_seconds", 120))
            if timeout < 1 or timeout > 900: raise HTTPException(400, f"命令超时必须在 1 到 900 秒")
            item["timeout_seconds"] = timeout
            mapping = item.get("result_cell")
            if not isinstance(mapping, dict) or not all(isinstance(mapping.get(key), int) and mapping[key] >= 0 for key in ("table", "row", "column")):
                raise HTTPException(400, f"命令 {item['command']} 的回填位置不合法")
        device["order"] = order
    rules = snapshot.get("non_command_rules", [])
    if not isinstance(rules, list): raise HTTPException(400, "非命令规则必须是数组")
    for rule in rules:
        if rule.get("mode") not in {"preserve", "fixed", "derived", "manual"}: raise HTTPException(400, "非命令规则模式不合法")
        mapping = rule.get("result_cell")
        if not isinstance(mapping, dict) or not all(isinstance(mapping.get(key), int) and mapping[key] >= 0 for key in ("table", "row", "column")):
            raise HTTPException(400, "非命令规则回填位置不合法")
        if rule["mode"] == "derived" and not str(rule.get("source_command", "")).strip(): raise HTTPException(400, "命令推导规则缺少来源命令")
    return snapshot

def merge_incremental_template(base_path: Path, added_path: Path, output_path: Path) -> int:
    """把增量文档中的设备表格追加到旧模板，保留原表格 OOXML 与样式。"""
    base = Document(base_path); added = Document(added_path)
    if len(base.sections) != len(added.sections): raise HTTPException(409, "增量模板版式不兼容，请使用完整替换")
    for left, right in zip(base.sections, added.sections):
        geometry = (left.page_width, left.page_height, left.left_margin, left.right_margin, left.orientation)
        other = (right.page_width, right.page_height, right.left_margin, right.right_margin, right.orientation)
        if geometry != other: raise HTTPException(409, "增量模板版式不兼容，请使用完整替换")
    offset = len(base.tables)
    for table in added.tables:
        base.element.body.insert(-1, deepcopy(table._element))
    temporary = output_path.with_suffix(".merged.docx"); base.save(temporary); shutil.move(temporary, output_path)
    return offset

def shift_table_mappings(snapshot: dict[str, Any], offset: int) -> None:
    for device in snapshot.get("devices", []):
        if "table_index" in device: device["table_index"] += offset
        for command in device.get("commands", []): command["result_cell"]["table"] += offset
    for rule in snapshot.get("non_command_rules", []): rule["result_cell"]["table"] += offset
