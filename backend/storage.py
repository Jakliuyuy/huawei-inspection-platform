"""任务产物与上传目录的磁盘管理。"""

from __future__ import annotations

import shutil
import sqlite3
import zipfile
from pathlib import Path

from backend.config import RECENT_UPLOAD_LOG_DIRNAME, RECENT_UPLOAD_LOG_KEEP_COUNT, config


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


def recent_upload_logs_root() -> Path:
    return config.upload_dir / RECENT_UPLOAD_LOG_DIRNAME


def prune_recent_upload_logs() -> None:
    root = recent_upload_logs_root()
    if not root.exists():
        return
    cache_dirs = sorted((path for path in root.iterdir() if path.is_dir()), key=lambda path: path.name, reverse=True)
    for path in cache_dirs[RECENT_UPLOAD_LOG_KEEP_COUNT:]:
        shutil.rmtree(path, ignore_errors=True)


def cache_recent_upload_logs(job_id: str, prepared_dir: Path) -> None:
    root = recent_upload_logs_root()
    root.mkdir(parents=True, exist_ok=True)
    target_dir = root / job_id
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
    shutil.copytree(prepared_dir, target_dir)
    prune_recent_upload_logs()


def sync_recent_upload_logs_from_existing() -> None:
    root = recent_upload_logs_root()
    root.mkdir(parents=True, exist_ok=True)
    job_dirs = sorted(
        (
            path for path in config.upload_dir.iterdir()
            if path.is_dir() and path.name != RECENT_UPLOAD_LOG_DIRNAME
        ),
        key=lambda path: path.name,
        reverse=True,
    )
    for job_dir in job_dirs[:RECENT_UPLOAD_LOG_KEEP_COUNT]:
        prepared_dir = job_dir / "prepared"
        if not prepared_dir.exists():
            continue
        target_dir = root / job_dir.name
        if target_dir.exists():
            continue
        shutil.copytree(prepared_dir, target_dir)
    prune_recent_upload_logs()


def create_bundle(output_dir: Path, bundle_path: Path) -> None:
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in output_dir.rglob("*"):
            if file.is_file() and file != bundle_path:
                archive.write(file, arcname=file.relative_to(output_dir))
