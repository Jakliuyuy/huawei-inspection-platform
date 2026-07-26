"""生成/刷新黄金基线。

用法：  py -3 tests/make_golden.py

只在两种情况下重跑：
  1. 首次建立基线（应在 tag pre-refactor-20260727 上执行）
  2. 有意变更了报告内容，且已人工确认差异符合预期

**重构期间不要随手刷新基线**——基线的全部价值就在于它不跟着代码一起变。
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import (  # noqa: E402
    GOLDEN_DATE,
    GOLDEN_DIR,
    REAL_LOG_ROOT,
    fingerprints_of,
    run_generation,
)


def main() -> int:
    if not REAL_LOG_ROOT.is_dir():
        print(f"ERROR: 找不到真实日志语料 {REAL_LOG_ROOT}")
        return 1

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="golden-"))
    try:
        print(f"日志语料 : {REAL_LOG_ROOT}")
        print(f"报告日期 : {GOLDEN_DATE}")
        print("生成中（串行，约需 1-2 分钟）...")
        summary = run_generation(tmp)

        prints = fingerprints_of(tmp)
        (GOLDEN_DIR / "fingerprints.json").write_text(
            json.dumps(prints, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        audit_src = Path(summary.output_dir) / "audit_matching_result.txt"
        shutil.copy2(audit_src, GOLDEN_DIR / "audit.txt")

        # docx 本体留一份到仓库外：指纹对不上时需要用 Word 打开看差异
        keep = Path(tempfile.gettempdir()) / "inspection-golden-docx"
        if keep.exists():
            shutil.rmtree(keep, ignore_errors=True)
        keep.mkdir(parents=True)
        for f in tmp.glob("*.docx"):
            shutil.copy2(f, keep / f.name)

        print(f"\n已写入 {GOLDEN_DIR}")
        for name, digest in sorted(prints.items()):
            print(f"  {digest[:12]}  {name}")
        print(f"\n共 {len(prints)} 份报告；audit {len((GOLDEN_DIR / 'audit.txt').read_text(encoding='utf-8').splitlines())} 行")
        print(f"docx 副本（供人工比对）: {keep}")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
