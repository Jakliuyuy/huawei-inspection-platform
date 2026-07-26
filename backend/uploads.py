"""上传落盘、解压与日志目录布局识别。"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from fastapi import HTTPException, UploadFile

from backend.config import (
    MAX_EXTRACTED_BYTES,
    MAX_EXTRACTED_FILES,
    MAX_UPLOAD_BYTES,
    SYSTEM_DIR_NAMES,
    now_local,
)


def sanitize_member_name(name: str) -> str:
    normalized = Path(name.replace("\\", "/"))
    if normalized.is_absolute() or ".." in normalized.parts:
        raise HTTPException(status_code=400, detail="压缩包中包含非法路径")
    return str(normalized)


def extract_zip_safe(zip_path: Path, target_dir: Path) -> None:
    extracted_files = 0
    extracted_bytes = 0
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            member_name = sanitize_member_name(member.filename)
            if not member_name:
                continue
            if member.is_dir():
                destination = target_dir / member_name
                destination.mkdir(parents=True, exist_ok=True)
                continue
            extracted_files += 1
            if extracted_files > MAX_EXTRACTED_FILES:
                raise HTTPException(status_code=400, detail="压缩包解压后的文件数量超出限制")
            extracted_bytes += member.file_size
            if extracted_bytes > MAX_EXTRACTED_BYTES:
                raise HTTPException(status_code=400, detail="压缩包解压后的总大小超出限制")
            destination = target_dir / member_name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as handle:
                shutil.copyfileobj(source, handle)


def is_supported_upload(path: Path) -> bool:
    return path.suffix.lower() in {".zip", ".log"}


def infer_system_dir_from_log_name(path: Path) -> str:
    stem_upper = path.stem.upper()
    for system_name in SYSTEM_DIR_NAMES:
        if stem_upper.startswith(system_name.upper() + "_"):
            return system_name
    return ""


def copy_uploaded_logs(saved_files: list[Path], target_dir: Path) -> bool:
    log_files = [path for path in saved_files if path.suffix.lower() == ".log"]
    if not log_files:
        return False

    has_nested_layout = any(len(path.relative_to(target_dir.parent / "input").parts) > 1 for path in log_files)
    if has_nested_layout:
        for log_file in log_files:
            relative_path = log_file.relative_to(target_dir.parent / "input")
            destination = target_dir / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(log_file, destination)
        return True

    date_dir = target_dir / now_local().strftime("%Y-%m-%d")
    date_dir.mkdir(parents=True, exist_ok=True)
    for log_file in log_files:
        system_dir = infer_system_dir_from_log_name(log_file)
        destination_dir = date_dir / system_dir if system_dir else date_dir
        destination_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(log_file, destination_dir / log_file.name)
    return True


def detect_log_root(path: Path) -> Path:
    candidates = [path]
    candidates.extend(child for child in path.iterdir() if child.is_dir())
    for candidate in candidates:
        if any((candidate / name).exists() for name in SYSTEM_DIR_NAMES):
            return candidate
    date_dirs = sorted(child for child in path.rglob("*") if child.is_dir() and "-" in child.name)
    if date_dirs:
        return date_dirs[0]
    raise HTTPException(status_code=400, detail="无法识别日志目录结构")


def save_uploads(job_dir: Path, files: list[UploadFile]) -> Path:
    input_dir = job_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    total_size = 0
    saved_files: list[Path] = []
    for upload in files:
        if not upload.filename:
            continue
        relative_name = sanitize_member_name(upload.filename)
        relative_path = Path(relative_name)
        if not is_supported_upload(relative_path):
            raise HTTPException(status_code=400, detail=f"不支持的文件类型: {upload.filename}")
        target = input_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as handle:
            while chunk := upload.file.read(1024 * 1024):
                total_size += len(chunk)
                if total_size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=400, detail="上传文件总大小超出限制")
                handle.write(chunk)
        saved_files.append(target)

    prepared_dir = job_dir / "prepared"
    prepared_dir.mkdir(parents=True, exist_ok=True)

    zip_files = [path for path in saved_files if path.suffix.lower() == ".zip"]
    copied_logs = copy_uploaded_logs(saved_files, prepared_dir)
    for zip_file in zip_files:
        extract_zip_safe(zip_file, prepared_dir)

    if zip_files or copied_logs:
        return prepared_dir
    raise HTTPException(status_code=400, detail="未发现可处理的日志文件")
