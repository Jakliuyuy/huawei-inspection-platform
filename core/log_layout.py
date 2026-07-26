"""日志目录布局识别与完整度统计。

预览与生成**必须**共用这里的目录解析和日志筛选，否则预览报出的
"GPRS 12/15" 与生成时实际读到的文件不是一回事，预览就在撒谎。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence


def system_dir_candidates(sys_key: str) -> list[str]:
    """一个系统可能对应的目录名。

    配置里键是 NM1/NM2/NM3，而现场目录常写成 NetMgmt1 等。
    """
    names = [sys_key]
    if sys_key.startswith("NM"):
        names.append(sys_key.replace("NM", "NetMgmt"))
    return names


def resolve_system_log_dir(log_root: Path, sys_key: str) -> Path | None:
    for name in system_dir_candidates(sys_key):
        candidate = log_root / name
        if candidate.exists():
            return candidate
    return None


def iter_system_logs(log_dir: Path) -> Iterator[Path]:
    """该系统目录下参与生成的日志文件。

    summary 文件不是设备日志，生成时会跳过，统计时也必须跳过——否则
    预览的"实到"会比实际参与匹配的多。
    """
    for path in sorted(log_dir.glob("*.log")):
        if "summary" in path.name:
            continue
        yield path


@dataclass
class SystemStat:
    key: str
    display_name: str
    expected: int
    actual: int
    has_logs: bool

    @property
    def missing(self) -> int:
        return max(self.expected - self.actual, 0)


def preview_system_stats(log_root: Path, configs: dict) -> list[SystemStat]:
    """逐系统统计实到/应到设备数。

    expected 取配置里的 hosts 数量；NM1-3 没有 hosts 清单，此时回落为
    实到数（完整度校验对它们不生效，这是配置缺失而非统计错误）。
    """
    stats: list[SystemStat] = []
    for key, info in configs.items():
        log_dir = resolve_system_log_dir(log_root, key)
        actual = len(list(iter_system_logs(log_dir))) if log_dir else 0
        expected = len(info.get("hosts", {}))
        stats.append(
            SystemStat(
                key=key,
                display_name=info.get("display_name", key),
                expected=expected if expected > 0 else actual,
                actual=actual,
                has_logs=actual > 0,
            )
        )
    return stats


def detect_log_root(base: Path, system_keys: Sequence[str]) -> Path | None:
    """在上传解压后的目录里找出真正的日志根。

    先看 base 自身与其直接子目录里是否含系统目录；都没有时回退到形似
    日期的目录，取**最新**的一个。
    """
    candidates = [base]
    candidates.extend(child for child in base.iterdir() if child.is_dir())
    for candidate in candidates:
        for key in system_keys:
            if resolve_system_log_dir(candidate, key) is not None:
                return candidate

    date_dirs = sorted(
        (child for child in base.rglob("*") if child.is_dir() and "-" in child.name),
        key=lambda path: path.name,
    )
    return date_dirs[-1] if date_dirs else None
