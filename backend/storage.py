"""任务产物与上传目录的磁盘管理。"""

from __future__ import annotations

import shutil
import sqlite3
import zipfile
from pathlib import Path

from backend.config import config


def delete_job_storage(job: sqlite3.Row) -> None:
    for field in ("input_path", "output_path", "bundle_path"):
        value = job[field]
        if not value:
            continue
        path = Path(value)
        if path.is_file():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
    # input_path 在准备阶段被改写成 prepared 子目录，需回溯到 uploads/<job_id> 整体清理
    input_value = job["input_path"]
    if input_value:
        input_path = Path(input_value)
        for candidate in (input_path, *input_path.parents):
            if candidate.name == job["id"] and candidate.parent == config.upload_dir:
                shutil.rmtree(candidate, ignore_errors=True)
                break


LEGACY_RECENT_LOGS_DIRNAME = "_recent_logs"


def remove_legacy_recent_logs_cache() -> None:
    """删掉早期版本留下的 _recent_logs 缓存。

    那份缓存每次上传都把 prepared/ 整棵复制一遍，却没有任何读取方，
    等于让磁盘占用翻倍。目录内容全部可从 uploads/<job_id>/prepared 还原。
    """
    legacy = config.upload_dir / LEGACY_RECENT_LOGS_DIRNAME
    if legacy.is_dir():
        shutil.rmtree(legacy, ignore_errors=True)


def create_bundle(output_dir: Path, bundle_path: Path) -> None:
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in output_dir.rglob("*"):
            if file.is_file() and file != bundle_path:
                archive.write(file, arcname=file.relative_to(output_dir))
