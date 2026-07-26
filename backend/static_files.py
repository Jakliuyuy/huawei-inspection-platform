"""前端静态文件托管。

线上仍由 Nginx 直发 /app/，容器里不带 dist 时这里自动跳过挂载；
本地把 dist 放进来，一条 python server.py 就能用，不必装 Nginx 或 Node。
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

from backend.config import config

logger = logging.getLogger(__name__)

MOUNT_PATH = "/app"


class SPAStaticFiles(StaticFiles):
    """带 history fallback 的静态文件。

    StaticFiles(html=True) 只会去找 404.html，找不到就抛 404 ——
    刷新 /app/tasks/20260727-001 这种深链会直接白屏。Nginx 那边靠
    try_files ... /app/index.html 兜住，这里要自己补上。
    """

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


def mount_frontend(app: FastAPI) -> bool:
    """挂载前端。必须在所有 /api 路由注册之后调用。"""
    directory = config.frontend_dir
    if not (directory / "index.html").is_file():
        logger.info("未找到前端产物 %s，跳过静态托管（线上由 Nginx 直发）", directory)
        return False
    app.mount(MOUNT_PATH, SPAStaticFiles(directory=str(directory), html=True), name="frontend")
    logger.info("已托管前端 %s -> %s", directory, MOUNT_PATH)
    return True
