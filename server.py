"""华为巡检云平台 —— 应用入口。

真正的实现都在 backend/ 下：
  config / db / security / auth / audit          基础设施
  queries / serializers / pagination / paths     数据与表示
  uploads / storage / downloads / jobs / mail    领域逻辑
  upload_sessions / static_files                 上传暂存与前端托管
  routes/                                        HTTP 路由

⚠️ 必须保留 __main__ 守卫：报告生成用 ProcessPoolExecutor，Windows 下
spawn 会重新导入主模块，没有守卫会递归启动 uvicorn。
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.config import APP_TITLE, config
from backend.db import cleanup_expired_data, initialize_database, recover_incomplete_jobs
from backend.queries import rebuild_report_file_index
from backend.routes import admin, auth, email, jobs, legacy, meta, uploads
from backend.static_files import mount_frontend
from backend.storage import remove_legacy_recent_logs_cache
from backend.upload_sessions import collect_garbage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    rebuild_report_file_index()
    recover_incomplete_jobs()
    cleanup_expired_data()
    collect_garbage()
    remove_legacy_recent_logs_cache()
    yield


app = FastAPI(title=APP_TITLE, lifespan=lifespan)

app.include_router(auth.router)
app.include_router(meta.router)
app.include_router(uploads.router)
app.include_router(jobs.router)
app.include_router(email.router)
app.include_router(admin.router)
app.include_router(legacy.router)

# 必须在 /api 路由之后：mount 会接管 /app 前缀下的所有请求
mount_frontend(app)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    # 本地模式免登录，绝不能暴露到局域网
    host = "127.0.0.1" if config.local_mode else "0.0.0.0"
    if config.local_mode:
        logger.info("本地模式已启用（免登录）。打开 http://localhost:%s/app/", port)
    uvicorn.run("server:app", host=host, port=port, reload=False)
