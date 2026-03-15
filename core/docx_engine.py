from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# 预编译核心正则，提升万次匹配速度
IP_RE = re.compile(r"(\d+\.\d+\.\d+\.[1-9]\d*)")
CMD_RE = re.compile(r"[>\]#]\s*((?:display|dis|show)\s+\S+.*?)\s*$", re.I)

@dataclass
class DeviceReport:
    host: str
    ip: str
    sections: dict[str, str]

def normalize(text: str) -> str:
    """极速归一化"""
    return "".join(filter(str.isalnum, text.lower()))

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

def select_command_output(sections: dict[str, str], wanted: str, cache: dict) -> str:
    """使用预计算缓存的秒级匹配"""
    wn = normalize(wanted)
    if wn in cache:
        cmd = cache[wn]
        return f"{cmd}\n{sections[cmd]}" if sections.get(cmd) else cmd

    # 仅在缓存失效时进行模糊匹配
    keyword_groups = [
        ("alarm", "active"), ("interface", "brief"), ("ip", "interface"), 
        ("cpu",), ("memory",), ("logbuffer",), ("version",)
    ]
    for kws in keyword_groups:
        if all(k in wn for k in kws):
            for cmd in sections:
                if all(k in normalize(cmd) for k in kws):
                    return f"{cmd}\n{sections[cmd]}" if sections[cmd] else cmd
    return "未匹配到对应日志输出"
