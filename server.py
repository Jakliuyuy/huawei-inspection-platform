"""华为巡检云平台 —— 应用入口。

真正的实现都在 backend/ 下：
  config / db / security / auth / audit          基础设施
  queries / serializers / pagination / paths     数据与表示
  uploads / storage / downloads / jobs / mail    领域逻辑
  routes/                                        HTTP 路由

⚠️ 必须保留 __main__ 守卫：报告生成用 ProcessPoolExecutor，Windows 下
spawn 会重新导入主模块，没有守卫会递归启动 uvicorn。
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.config import APP_TITLE
from backend.db import cleanup_expired_data, initialize_database, recover_incomplete_jobs
from backend.queries import rebuild_report_file_index
from backend.routes import admin, auth, email, jobs, legacy, meta
from backend.storage import prune_recent_upload_logs, sync_recent_upload_logs_from_existing


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    rebuild_report_file_index()
    recover_incomplete_jobs()
    cleanup_expired_data()
    sync_recent_upload_logs_from_existing()
    prune_recent_upload_logs()
    yield


app = FastAPI(title=APP_TITLE, lifespan=lifespan)

app.include_router(auth.router)
app.include_router(meta.router)
app.include_router(jobs.router)
app.include_router(email.router)
app.include_router(admin.router)
app.include_router(legacy.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=int(os.getenv("PORT", "8080")), reload=False)
