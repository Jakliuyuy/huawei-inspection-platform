from __future__ import annotations

import json
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from docx import Document

from core import docx_engine as engine

RE_IP = re.compile(r"(\d+\.\d+\.\d+\.[1-9]\d*)")
RE_DATE = re.compile(r"\d{4}[-]?\d{2}[-]?\d{2}|\d{2}月\d{2}日")


@dataclass
class ReportPaths:
    root: Path
    config_path: Path
    logs_base: Path
    templates_dir: Path
    output_base: Path


@dataclass
class GenerationSummary:
    target_date: str
    log_root: str
    output_dir: str
    generated_files: list[str]
    audit_lines: list[str]


class LogObject:
    def __init__(self, path: Path, all_config: dict):
        self.filename = path.name
        self.text = self._read_safe(path)
        self.sections = engine.parse_sections(self.text)
        self.norm_cache = {engine.normalize(cmd): cmd for cmd in self.sections}

        match = re.search(r"<([^>\n\s]+)>", self.text)
        host = match.group(1).strip() if match else ""
        self.real_hostname = host.split("<")[1] if host.startswith(("HRP_M<", "HRP_S<")) else host

        ips_in_name = RE_IP.findall(self.filename)
        self.filename_ip = next(
            (ip for ip in ips_in_name if not ip.startswith(("127.", "0.", "1.23.", "1.3."))),
            "",
        )
        self.content_ips = set(RE_IP.findall(self.text))

        stem = path.stem
        parts = stem.split("_")
        prefix = parts[0].upper() if parts else ""
        is_sys_prefix = any(key in prefix for key in list(all_config.keys()) + ["NETMGMT", "NM", "SMS", "GPRS"])
        self.file_subject = (parts[1] if len(parts) >= 2 and is_sys_prefix else parts[0]).lower()

    @staticmethod
    def _read_safe(path: Path) -> str:
        for encoding in ("utf-8", "gbk", "gb18030"):
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        return path.read_text(encoding="utf-8", errors="ignore")


def default_paths(root: Path | None = None) -> ReportPaths:
    if root is None:
        root = Path(__file__).resolve().parents[1]
    return ReportPaths(
        root=root,
        config_path=root / "config.json",
        logs_base=root / "Logs_待处理",
        templates_dir=root / "Word_模板库",
        output_base=root / "巡检报告",
    )


def load_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def find_latest_log_dir(logs_base: Path) -> Path:
    date_dirs = sorted(path for path in logs_base.iterdir() if path.is_dir() and "-" in path.name)
    if not date_dirs:
        raise FileNotFoundError(f"未在 {logs_base} 发现日期目录")
    return date_dirs[-1]


def safe_update_paragraph(paragraph, new_text: str) -> None:
    if not paragraph.runs:
        paragraph.text = str(new_text)
        return
    paragraph.runs[0].text = str(new_text)
    for run in paragraph.runs[1:]:
        run.text = ""


def find_match(log_pool: list[LogObject], target_ip: str, template_host: str, config_host: str) -> tuple[LogObject | None, str]:
    template_host = template_host.lower()
    config_host = config_host.lower()

    if target_ip:
        for index, log in enumerate(log_pool):
            if target_ip == log.filename_ip:
                return log_pool.pop(index), f"文件同IP({target_ip})"

    for target in (config_host, template_host):
        if not target or len(target) < 3:
            continue
        for index, log in enumerate(log_pool):
            if target == log.real_hostname.lower():
                return log_pool.pop(index), f"设备名全等({log.real_hostname})"

    for target in (config_host, template_host):
        if not target or len(target) < 3:
            continue
        for index, log in enumerate(log_pool):
            subject = log.file_subject
            if target == subject or (target in subject and target[-3:] == subject[-3:]) or (subject in target and subject[-3:] == target[-3:]):
                return log_pool.pop(index), f"业务代号({log.file_subject})"

    if target_ip:
        for index, log in enumerate(log_pool):
            if target_ip in log.content_ips:
                return log_pool.pop(index), f"日志内容IP({target_ip})"

    return None, ""


def process_system(
    sys_key: str,
    sys_info: dict,
    log_root: Path,
    output_dir: Path,
    target_date: str,
    all_configs: dict,
    templates_dir: Path,
) -> tuple[list[str], list[str]]:
    audit_lines = [f"\n=== {sys_info['display_name']} ==="]
    generated_files: list[str] = []
    log_dir = log_root / sys_key
    if not log_dir.exists():
        log_dir = log_root / sys_key.replace("NM", "NetMgmt")
        if not log_dir.exists():
            return audit_lines, generated_files

    log_pool = [LogObject(path, all_configs) for path in log_dir.glob("*.log") if "summary" not in path.name]
    template_file = templates_dir / sys_info["template"]
    if not template_file.exists():
        return [f"× {sys_key}: 找不到模板 {template_file.name}"], generated_files

    doc = Document(template_file)
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if sys_info.get("is_dual_title") and "网管网络设备" in text:
            safe_update_paragraph(paragraph, sys_info["display_name"])
        elif "日巡检报告" in text:
            safe_update_paragraph(paragraph, f"{sys_info['display_name']}{target_date}日巡检报告")
        elif RE_DATE.search(text):
            safe_update_paragraph(paragraph, RE_DATE.sub(target_date, text))

    for index, table in enumerate(doc.tables, 1):
        target_ip = ""
        template_host = ""
        for row in table.rows[:2]:
            for cell in row.cells:
                match = RE_IP.search(cell.text)
                if match:
                    target_ip = match.group(1)
                if any(keyword in cell.text for keyword in ["型号", "名称", "设备"]):
                    parts = re.split(r"[:：]", cell.text)
                    template_host = parts[1].strip() if len(parts) > 1 else ""

        config_host = sys_info.get("hosts", {}).get(str(index), "")
        log, reason = find_match(log_pool, target_ip, template_host, config_host)
        if not log:
            audit_lines.append(f"× [{index:02d}] 匹配失败 (IP:{target_ip}, Host:{template_host or config_host})")
            continue

        audit_lines.append(f"√ [{index:02d}] 命中 {log.filename} via {reason}")
        for row_index, row in enumerate(table.rows):
            cells = row.cells
            if row_index == 1:
                for cell in cells:
                    if "IP" in cell.text.upper():
                        match = RE_IP.search(cell.text)
                        resolved_ip = match.group(1) if match and not match.group(1).startswith("127.") else log.filename_ip
                        engine.set_cell_text(cell, f"IP: {resolved_ip or '待补充'}")
                    elif RE_DATE.search(cell.text) or cell.text.strip().isdigit():
                        engine.set_cell_text(cell, target_date.replace("-", ""))
            elif row_index == 2:
                for cell in cells[1:]:
                    if not cell.text.strip() or cell.text in ["杜康", "刘关雷"]:
                        engine.set_cell_text(cell, "杜康")
            elif row_index >= 4 and len(cells) >= 3:
                wanted = cells[1].text.strip()
                if wanted:
                    engine.set_cell_text(cells[2], engine.select_command_output(log.sections, wanted, log.norm_cache))

    file_name = f"{(sys_key if sys_info.get('is_english_name') else sys_info['display_name'])}{target_date}日巡检报告.docx"
    output_path = output_dir / file_name
    doc.save(output_path)
    generated_files.append(str(output_path))
    return audit_lines, generated_files


def generate_reports(
    *,
    paths: ReportPaths,
    log_root: Path | None = None,
    target_date: str | None = None,
    output_dir: Path | None = None,
    max_workers: int | None = None,
    progress_callback: Callable[[int, int, str, dict], None] | None = None,
) -> GenerationSummary:
    configs = load_config(paths.config_path)
    log_root = log_root or find_latest_log_dir(paths.logs_base)
    target_date = target_date or datetime.now().strftime("%Y-%m-%d")
    output_dir = output_dir or (paths.output_base / target_date)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_audit: list[str] = []
    generated_files: list[str] = []
    total_systems = len(configs)
    worker_count = max_workers or min(4, max(1, len(configs)))
    if worker_count <= 1:
        for completed_count, (key, value) in enumerate(configs.items(), 1):
            audit_lines, files = process_system(key, value, log_root, output_dir, target_date, configs, paths.templates_dir)
            all_audit.extend(audit_lines)
            generated_files.extend(files)
            if progress_callback is not None:
                progress_callback(completed_count, total_systems, key, value)
    else:
        try:
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                futures = {
                    executor.submit(process_system, key, value, log_root, output_dir, target_date, configs, paths.templates_dir): key
                    for key, value in configs.items()
                }
                for completed_count, future in enumerate(as_completed(futures), 1):
                    key = futures[future]
                    audit_lines, files = future.result()
                    all_audit.extend(audit_lines)
                    generated_files.extend(files)
                    if progress_callback is not None:
                        progress_callback(completed_count, total_systems, key, configs[key])
        except PermissionError:
            for completed_count, (key, value) in enumerate(configs.items(), 1):
                audit_lines, files = process_system(key, value, log_root, output_dir, target_date, configs, paths.templates_dir)
                all_audit.extend(audit_lines)
                generated_files.extend(files)
                if progress_callback is not None:
                    progress_callback(completed_count, total_systems, key, value)

    (output_dir / "audit_matching_result.txt").write_text("\n".join(all_audit), encoding="utf-8")
    return GenerationSummary(
        target_date=target_date,
        log_root=str(log_root),
        output_dir=str(output_dir),
        generated_files=generated_files,
        audit_lines=all_audit,
    )
