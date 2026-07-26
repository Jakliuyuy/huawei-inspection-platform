"""任务执行：线程池、进度回写与报告生成编排。"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from backend.audit import record_audit
from backend.config import LOCAL_TZ, config, now_local
from backend.db import cleanup_expired_data, db_connect
from backend.reports import sync_job_report_files
from backend.storage import create_bundle
from backend.uploads import detect_log_root
from core.report_service import ReportPaths, generate_reports

job_executor = ThreadPoolExecutor(max_workers=config.max_job_workers)


def update_job(job_id: str, **fields: Any) -> None:
    if not fields:
        return
    columns = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [job_id]
    conn = db_connect()
    with conn:
        conn.execute(f"UPDATE jobs SET {columns} WHERE id = ?", values)
    conn.close()


def process_job(job_id: str, user_id: int) -> None:
    try:
        cleanup_expired_data()
        conn = db_connect()
        job = conn.execute(
            """
            SELECT jobs.*, users.username
            FROM jobs JOIN users ON users.id = jobs.user_id
            WHERE jobs.id = ?
            """,
            (job_id,),
        ).fetchone()
        conn.close()
        if not job:
            return

        input_path = Path(job["input_path"])
        output_dir = config.report_dir / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        update_job(
            job_id,
            status="running",
            progress=5,
            status_detail="正在识别日志目录",
            started_at=now_local().isoformat(),
        )

        log_root = detect_log_root(input_path)

        def report_progress(completed_count: int, total_count: int, sys_key: str, sys_info: dict[str, Any]) -> None:
            base = 10
            span = 80
            progress = base + round((completed_count / max(total_count, 1)) * span)
            update_job(
                job_id,
                progress=progress,
                status_detail=f"正在生成 {sys_info['display_name']}（{completed_count}/{total_count}）",
            )

        update_job(job_id, progress=10, status_detail="已识别日志目录，开始生成报告")
        summary = generate_reports(
            paths=ReportPaths(
                root=config.app_root,
                config_path=config.config_path,
                logs_base=log_root.parent if log_root.parent.exists() else input_path,
                templates_dir=config.template_dir,
                output_base=output_dir,
            ),
            log_root=log_root,
            output_dir=output_dir,
            target_date=now_local().strftime("%Y-%m-%d"),
            max_workers=max(1, config.max_job_workers),
            progress_callback=report_progress,
        )
        update_job(job_id, progress=95, status_detail="正在打包结果文件")
        bundle_path = output_dir / f"{job_id}.zip"
        create_bundle(output_dir, bundle_path)
        update_job(
            job_id,
            status="completed",
            progress=100,
            status_detail="报告生成完成",
            output_path=str(output_dir),
            bundle_path=str(bundle_path),
            log_root=summary.log_root,
            finished_at=now_local().isoformat(),
            generated_files=json.dumps(summary.generated_files, ensure_ascii=False),
            error_message=None,
        )
        conn = db_connect()
        try:
            with conn:
                sync_job_report_files(
                    conn,
                    job_id=job_id,
                    user_id=user_id,
                    username=job["username"],
                    report_date=now_local().strftime("%Y-%m-%d"),
                    generated_files=summary.generated_files,
                    created_at=job["created_at"],
                    local_tz=LOCAL_TZ,
                )
        finally:
            conn.close()
        record_audit(user_id, "job_completed", f"任务 {job_id} 完成，生成 {len(summary.generated_files)} 个文件")
    except Exception as exc:
        update_job(
            job_id,
            status="failed",
            progress=100,
            status_detail="任务执行失败",
            finished_at=now_local().isoformat(),
            error_message=str(exc),
        )
        record_audit(user_id, "job_failed", f"任务 {job_id} 失败: {exc}")


def enqueue_job(job_id: str, user_id: int) -> None:
    job_executor.submit(process_job, job_id, user_id)
