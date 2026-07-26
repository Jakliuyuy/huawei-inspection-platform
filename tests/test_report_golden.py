"""报告生成的黄金基线回归。

这是整个重构期间最重要的一道防线：Phase 2 是纯搬运，指纹**必须完全一致**，
任何一处不同都说明搬错了。指纹对不上且查不出原因时，立刻 git bisect，
不要继续往前搬。
"""

from __future__ import annotations

import difflib
import json
from pathlib import Path

import pytest

from conftest import (
    GOLDEN_DIR,
    fingerprints_of,
    requires_golden,
    requires_real_logs,
    run_generation,
)

pytestmark = [requires_real_logs, requires_golden]


@pytest.fixture(scope="module")
def generated(tmp_path_factory) -> Path:
    """整个模块只跑一次生成（约 1-2 分钟）。"""
    out = tmp_path_factory.mktemp("generated")
    run_generation(out)
    return out


def _golden_fingerprints() -> dict[str, str]:
    return json.loads((GOLDEN_DIR / "fingerprints.json").read_text(encoding="utf-8"))


def test_report_set_unchanged(generated: Path):
    """生成的报告文件名集合与基线一致。"""
    assert sorted(fingerprints_of(generated)) == sorted(_golden_fingerprints())


def test_report_contents_unchanged(generated: Path):
    """每份报告的文本指纹与基线一致。"""
    actual = fingerprints_of(generated)
    golden = _golden_fingerprints()

    drifted = [name for name in golden if actual.get(name) != golden[name]]
    if drifted:
        pytest.fail(
            "以下报告内容已变化：\n  "
            + "\n  ".join(drifted)
            + "\n\n若是有意变更，人工确认差异后重跑 tests/make_golden.py。"
            "\n若非有意变更，用 audit 差异定位（见 test_audit_log_unchanged）。"
        )


def test_audit_log_unchanged(generated: Path):
    """匹配审计逐行一致——指纹变化时靠它定位到具体系统/设备。"""
    actual = (generated / "audit_matching_result.txt").read_text(encoding="utf-8").splitlines()
    golden = (GOLDEN_DIR / "audit.txt").read_text(encoding="utf-8").splitlines()

    if actual != golden:
        diff = list(difflib.unified_diff(golden, actual, "golden", "actual", lineterm="", n=1))
        pytest.fail("匹配审计已变化：\n" + "\n".join(diff[:60]))


def test_all_systems_generated(generated: Path):
    """9 个系统全部产出报告——防止某个系统静默失败。"""
    assert len(fingerprints_of(generated)) == 9


@pytest.mark.parametrize("subset", [{"TOC"}, {"GPRS", "SMS"}])
def test_selective_generation_matches_full_run(generated: Path, tmp_path: Path, subset: set[str]):
    """选择性生成的产物必须与全量跑出的对应报告逐字节一致。

    这条断言锁住了一个具体陷阱：generate_reports 会把整份 config 作为
    all_configs 传给 process_system，最终喂给 LogObject.__init__，参与
    解析日志文件名（core/report_service.py:122-123）。因此实现 only_systems
    时**只能过滤遍历集合，all_configs 必须始终传全量**。
    如果哪天有人"顺手"改成过滤 config，这条会立刻变红。
    """
    from core.report_service import generate_reports

    if "only_systems" not in generate_reports.__code__.co_varnames:
        pytest.skip("only_systems 尚未实现（Phase 3）")

    out = tmp_path / "subset"
    run_generation(out, only_systems=subset)

    partial = fingerprints_of(out)
    full = fingerprints_of(generated)

    assert partial, f"{subset} 未产出任何报告"
    assert len(partial) == len(subset), f"期望 {len(subset)} 份，实际 {len(partial)} 份"
    for name, digest in partial.items():
        assert name in full, f"{name} 不在全量产物中"
        assert digest == full[name], f"{name} 在子集模式下内容与全量不一致"
