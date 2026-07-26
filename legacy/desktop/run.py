import argparse
import io
import json
import shutil
import sys
import zipfile
from pathlib import Path
from datetime import datetime

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR / "huawei-inspection-platform"
LOGS_BASE = SCRIPT_DIR / "Logs_待处理"
OUTPUT_BASE = SCRIPT_DIR / "巡检报告"
TEMP_DIR = SCRIPT_DIR / ".temp_extracted"

sys.path.insert(0, str(PROJECT_DIR))

from core import generate_reports
from core.report_service import ReportPaths

KNOWN_SYSTEMS = ["TOC", "TOB", "GPRS", "Softswitch", "SMS", "IntelligentNet", "NM1", "NM2", "NM3", "NetMgmt1", "NetMgmt2", "NetMgmt3"]

TEMP_KEEP_DAYS = 7

# ---------------------------------------------------------------------------
# 进度条
# ---------------------------------------------------------------------------
BAR_LEN = 36


def draw_bar(current: int, total: int, label: str = "") -> str:
    filled = int(BAR_LEN * current / max(total, 1))
    pct = current * 100 // max(total, 1)
    bar = "#" * filled + "-" * (BAR_LEN - filled)
    return f"\r  [{bar}] {pct:3d}%  {label}"


def progress_callback(completed: int, total: int, key: str, info: dict) -> None:
    sys.stdout.write(draw_bar(completed, total, info["display_name"]))
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# ZIP 处理
# ---------------------------------------------------------------------------
def extract_zip(zip_path: Path) -> Path:
    """解压 ZIP 并返回解压后的根目录路径"""
    dest = TEMP_DIR / zip_path.stem
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)

    print(f"  Extracting: {zip_path.name} ...", end=" ", flush=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)
    print("OK")

    entries = list(dest.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return dest


def cleanup_temp_dirs(keep: Path | None = None) -> None:
    """清理 .temp_extracted 下超过 TEMP_KEEP_DAYS 天未使用的解压目录（keep 及其父目录保留）"""
    if not TEMP_DIR.exists():
        return
    deadline = datetime.now().timestamp() - TEMP_KEEP_DAYS * 86400
    for p in TEMP_DIR.iterdir():
        try:
            if not p.is_dir():
                continue
            if keep is not None and (keep == p or keep.is_relative_to(p)):
                continue
            if p.stat().st_mtime < deadline:
                shutil.rmtree(p, ignore_errors=True)
        except OSError:
            pass


def has_log_subdirs(path: Path) -> bool:
    subdirs = {p.name for p in path.iterdir() if p.is_dir()}
    return bool(subdirs & set(KNOWN_SYSTEMS))


def find_log_root() -> Path | None:
    """在 Logs_待处理 下自动识别日志根目录"""
    if not LOGS_BASE.exists():
        return None

    zips = list(LOGS_BASE.glob("*.zip"))
    date_dirs = sorted(
        p for p in LOGS_BASE.iterdir() if p.is_dir() and any(c.isdigit() for c in p.name)
    )

    # 优先解压 ZIP
    if zips:
        zip_path = max(zips, key=lambda p: p.stat().st_mtime)
        return extract_zip(zip_path)

    # 查找日期目录
    if date_dirs:
        for d in reversed(date_dirs):
            if has_log_subdirs(d):
                return d

    # 直接在 Logs_待处理 下查找
    if has_log_subdirs(LOGS_BASE):
        return LOGS_BASE

    return None


# ---------------------------------------------------------------------------
# 主逻辑
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Huawei Inspection Report Generator")
    parser.add_argument(
        "log_dir",
        nargs="?",
        default=None,
        help="Log directory path (default: auto-detect ZIP or dir in Logs_待处理)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help=f"Output directory (default: {OUTPUT_BASE})",
    )
    parser.add_argument(
        "-d", "--date",
        default=None,
        help="Report date (default: today, format: YYYY-MM-DD)",
    )
    parser.add_argument(
        "-w", "--workers",
        default=0,
        type=int,
        help="Parallel workers (default: 4, set 1 for single-thread)",
    )
    parser.add_argument(
        "-s", "--system",
        action="append",
        default=[],
        metavar="KEY",
        help="Only process this system (repeatable). e.g. -s TOC -s GPRS",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available systems and exit",
    )
    args = parser.parse_args()

    report_date = args.date or datetime.now().strftime("%Y-%m-%d")
    try:
        datetime.strptime(report_date, "%Y-%m-%d")
    except ValueError:
        print(f"ERROR: invalid date - {report_date} (expected format: YYYY-MM-DD)")
        sys.exit(1)

    config_path = PROJECT_DIR / "config" / "report.json"
    templates_dir = PROJECT_DIR / "assets" / "templates"

    if not config_path.exists():
        print(f"ERROR: config file not found - {config_path}")
        sys.exit(1)

    if args.list:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        print("Available systems:")
        for key, info in cfg.items():
            template = info.get("template", "?")
            host_count = len(info.get("hosts", {}))
            print(f"  {key:16s}  {info['display_name']:24s}  {template:28s}  {host_count} hosts")
        sys.exit(0)

    if args.system:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        unknown = set(args.system) - set(cfg.keys())
        if unknown:
            print(f"ERROR: unknown system(s): {', '.join(sorted(unknown))}")
            print(f"Available: {', '.join(cfg.keys())}")
            sys.exit(1)
        filtered = {k: v for k, v in cfg.items() if k in args.system}
        config_path = TEMP_DIR / "report_filtered.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(filtered, f, ensure_ascii=False, indent=2)

    if not templates_dir.exists() or not any(templates_dir.iterdir()):
        print(f"ERROR: template dir empty or missing - {templates_dir}")
        sys.exit(1)

    # 确定日志根目录
    if args.log_dir:
        log_root = Path(args.log_dir).resolve()
        if not log_root.exists():
            print(f"ERROR: log dir not found - {log_root}")
            sys.exit(1)
    else:
        log_root = find_log_root()
        if log_root is None:
            print("ERROR: No log files found. Please:")
            print(f"  1. Put a ZIP file in {LOGS_BASE}/, e.g. {LOGS_BASE}/2026-7-24.zip")
            print(f"  2. Or put log directories in {LOGS_BASE}/ with this structure:")
            for sys_name in ["TOC", "TOB", "GPRS", "Softswitch", "SMS", "IntelligentNet", "NM1", "NM2", "NM3"]:
                print(f"     -- {sys_name}/  (.log files)")
            print(f"  3. Or specify directly: python run.py <log_dir>")
            sys.exit(1)

    output_dir = Path(args.output).resolve() if args.output else None

    print(f"Log dir  : {log_root}")
    print(f"Templates: {templates_dir}")
    print(f"Config   : {config_path}")
    workers = args.workers or min(4, 9)
    print(f"Workers  : {workers}")
    print()

    print("=" * 50)
    print(f"  Huawei Inspection Report - {report_date}")
    print("=" * 50)
    print()

    paths = ReportPaths(
        root=PROJECT_DIR,
        config_path=config_path,
        logs_base=log_root.parent if log_root.parent.exists() else log_root,
        templates_dir=templates_dir,
        output_base=output_dir or (OUTPUT_BASE / report_date),
    )

    summary = generate_reports(
        paths=paths,
        log_root=log_root,
        target_date=report_date,
        output_dir=output_dir or (OUTPUT_BASE / report_date),
        progress_callback=progress_callback,
        max_workers=args.workers or None,
    )

    print()
    print()
    print("=" * 50)
    print(f"  DONE!")
    print("=" * 50)
    print(f"  Output   : {summary.output_dir}")
    print(f"  Reports  : {len(summary.generated_files)}")
    for f in sorted(summary.generated_files):
        print(f"    - {Path(f).name}")
    print(f"  Audit log: {summary.output_dir}/audit_matching_result.txt")

    if str(log_root).startswith(str(TEMP_DIR)):
        print(f"\n(Temp dir: {log_root})")

    cleanup_temp_dirs(keep=log_root)


if __name__ == "__main__":
    main()
