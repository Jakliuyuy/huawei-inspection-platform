from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# 预编译核心正则，提升万次匹配速度
IP_RE = re.compile(r"(\d+\.\d+\.\d+\.[1-9]\d*)")
CMD_RE = re.compile(r"[>\]#]\s*((?:display|dis|show)\s+\S+.*?)\s*$", re.I)
CLI_ERROR_PATTERNS = (
    re.compile(r"^\s*\^\s*$", re.M),
    re.compile(r"unknown command", re.I),
    re.compile(r"unrecognized command", re.I),
    re.compile(r"^\s*%?\s*error:\s*$", re.I | re.M),
    re.compile(r"wrong parameter", re.I),
    re.compile(r"incomplete command", re.I),
    re.compile(r"ambiguous command", re.I),
    re.compile(r"too many parameters", re.I),
)

@dataclass
class DeviceReport:
    host: str
    ip: str
    sections: dict[str, str]

def normalize(text: str) -> str:
    """极速归一化"""
    return "".join(filter(str.isalnum, text.lower()))


CPU_COMMAND_PATTERNS = (
    ("displaycpu", 0),
    ("discpu", 0),
    ("showcpu", 0),
    ("displaycpuusage", 1),
    ("discpuusage", 1),
    ("showcpuusage", 1),
)

MEMORY_COMMAND_PATTERNS = (
    ("displaymemory", 0),
    ("dismemory", 0),
    ("showmemory", 0),
    ("displaymemoryusage", 1),
    ("dismemoryusage", 1),
    ("showmemoryusage", 1),
    ("displaymemoryall", 2),
    ("dismemoryall", 2),
    ("showmemoryall", 2),
)

INTELLIGENT_NET_SPECIAL_HOSTS = {
    "xzydvpnrt01",
    "xzydvpnrt02",
}

INTELLIGENT_NET_SPECIAL_IPS = {
    "10.143.45.31",
    "10.143.45.32",
}


def _strip_command_prefix(normalized: str) -> str:
    for prefix in ("display", "dis", "show"):
        if normalized.startswith(prefix):
            return normalized[len(prefix):]
    return normalized


def _get_command_family(wanted_normalized: str) -> str | None:
    if "cpu" in wanted_normalized:
        return "cpu"
    if "memory" in wanted_normalized:
        return "memory"
    return None


def _collect_family_outputs(sections: dict[str, str], family: str) -> list[str]:
    patterns = CPU_COMMAND_PATTERNS if family == "cpu" else MEMORY_COMMAND_PATTERNS
    collected: dict[str, tuple[int, str, str, bool]] = {}

    for command, output in sections.items():
        normalized = normalize(command)
        for prefix, order in patterns:
            if normalized.startswith(prefix):
                alias_key = _strip_command_prefix(normalized)
                content = f"{command}\n{output}" if output else command
                candidate = (order, normalized, content, _is_command_output_valid(output))
                existing = collected.get(alias_key)
                if existing is None or (candidate[3] and not existing[3]):
                    collected[alias_key] = candidate
                break

    ordered = sorted(collected.values(), key=lambda item: (item[0], item[1]))
    valid_outputs = [item[2] for item in ordered if item[3]]
    return valid_outputs


def _pick_best_command(sections: dict[str, str], commands: list[str]) -> str | None:
    valid_commands = [cmd for cmd in commands if _is_command_output_valid(sections.get(cmd, ""))]
    if not valid_commands:
        return None
    return min(valid_commands, key=normalize)


def _format_command_output(sections: dict[str, str], command: str) -> str:
    output = sections.get(command, "")
    return f"{command}\n{output}" if output else command


def _find_keyword_match(sections: dict[str, str], wanted_normalized: str) -> str | None:
    keyword_groups = [
        ("alarm", "active"), ("interface", "brief"), ("ip", "interface"), ("device",),
        ("cpu",), ("memory",), ("logbuffer",), ("version",)
    ]
    for kws in keyword_groups:
        if all(k in wanted_normalized for k in kws):
            matches = [cmd for cmd in sections if all(k in normalize(cmd) for k in kws)]
            best = _pick_best_command(sections, matches)
            if best:
                return best

    return None


def _find_alias_match(sections: dict[str, str], wanted_suffix: str) -> str | None:
    if not wanted_suffix:
        return None

    exact_alias_matches = [cmd for cmd in sections if _strip_command_prefix(normalize(cmd)) == wanted_suffix]
    best = _pick_best_command(sections, exact_alias_matches)
    if best:
        return best

    prefix_alias_matches = [cmd for cmd in sections if _strip_command_prefix(normalize(cmd)).startswith(wanted_suffix)]
    best = _pick_best_command(sections, prefix_alias_matches)
    if best:
        return best

    return _find_keyword_match(sections, wanted_suffix)


def _is_intelligent_net_special_device(system_key: str, template_host: str, target_ip: str) -> bool:
    if system_key != "IntelligentNet":
        return False
    if target_ip in INTELLIGENT_NET_SPECIAL_IPS:
        return True
    return normalize(template_host) in INTELLIGENT_NET_SPECIAL_HOSTS


def _find_intelligent_net_special_match(
    sections: dict[str, str],
    wanted_normalized: str,
    *,
    system_key: str,
    template_host: str,
    target_ip: str,
) -> str | None:
    if not _is_intelligent_net_special_device(system_key, template_host, target_ip):
        return None

    wanted_suffix = _strip_command_prefix(wanted_normalized)
    if "ipinterface" not in wanted_normalized and wanted_suffix in {"interface", "interfacebrief"}:
        preferred_matches = [
            cmd for cmd in sections
            if normalize(cmd) in {"displayinterface", "disinterface", "showinterface"}
        ]
        best = _pick_best_command(sections, preferred_matches)
        if best:
            return best
        fallback_matches = [
            cmd for cmd in sections
            if normalize(cmd) in {"displayinterfacebrief", "disinterfacebrief", "showinterfacebrief"}
        ]
        best = _pick_best_command(sections, fallback_matches)
        if best:
            return best

    if "device" in wanted_normalized:
        manu_matches = [
            cmd for cmd in sections
            if "device" in normalize(cmd) and "man" in normalize(cmd)
        ]
        best = _pick_best_command(sections, manu_matches)
        if best:
            return best
        fallback_matches = [
            cmd for cmd in sections
            if normalize(cmd) in {"displaydevice", "disdevice", "showdevice"}
        ]
        best = _pick_best_command(sections, fallback_matches)
        if best:
            return best

    return None


def _is_command_output_valid(output: str) -> bool:
    text = output.strip()
    if not text:
        return False
    return not any(pattern.search(text) for pattern in CLI_ERROR_PATTERNS)

def parse_sections(text: str) -> dict[str, str]:
    """高性能分段"""
    sections: dict[str, str] = {}
    current_cmd = None
    current_output = []

    for line in text.splitlines():
        if not line.strip(): continue
        match = CMD_RE.search(line)
        if match:
            if current_cmd: sections[current_cmd] = "\n".join(current_output).strip()
            current_cmd = match.group(1).strip()
            current_output = []
        elif current_cmd:
            current_output.append(line)

    if current_cmd: sections[current_cmd] = "\n".join(current_output).strip()
    return sections

def set_cell_text(cell, text):
    """极致填充：保留样式的同时最小化 XML 操作"""
    if not cell.paragraphs:
        cell.add_paragraph(str(text))
        return
    p = cell.paragraphs[0]
    if p.runs:
        p.runs[0].text = str(text)
        for r in p.runs[1:]: r.text = ""
    else:
        p.text = str(text)
    # 物理移除多余段落
    if len(cell.paragraphs) > 1:
        for i in range(len(cell.paragraphs)-1, 0, -1):
            p_el = cell.paragraphs[i]._element
            p_el.getparent().remove(p_el)

def select_command_output(
    sections: dict[str, str],
    wanted: str,
    cache: dict,
    *,
    system_key: str = "",
    template_host: str = "",
    target_ip: str = "",
) -> str:
    """使用预计算缓存的秒级匹配"""
    wn = normalize(wanted)
    family = _get_command_family(wn)
    if family:
        family_outputs = _collect_family_outputs(sections, family)
        if family_outputs:
            return "\n\n".join(family_outputs)

    if wn in cache:
        cmd = cache[wn]
        if _is_command_output_valid(sections.get(cmd, "")):
            return _format_command_output(sections, cmd)

    special_match = _find_intelligent_net_special_match(
        sections,
        wn,
        system_key=system_key,
        template_host=template_host,
        target_ip=target_ip,
    )
    if special_match:
        return _format_command_output(sections, special_match)

    wanted_suffix = _strip_command_prefix(wn)
    alias_match = _find_alias_match(sections, wanted_suffix)
    if alias_match:
        return _format_command_output(sections, alias_match)

    keyword_match = _find_keyword_match(sections, wn)
    if keyword_match:
        return _format_command_output(sections, keyword_match)

    return "未匹配到对应日志输出"
