"""文件下载响应。

⚠️ 这是对 Nginx 的隐性契约的唯一承载点。X-Accel-Redirect 分支把路径
相对 config.report_dir 拼成 /_protected-reports/...，交给 Nginx 的
internal alias 直接发送。改动 data/reports/ 的目录布局会让线上下载
静默 404，而本地开发（无 X-Forwarded-For）走 FileResponse 分支，
**本地永远测不出来**。
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException, Request, Response
from fastapi.responses import FileResponse

from backend.config import config


def build_download_response(request: Request, path: Path, download_name: str) -> Response:
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    # 直连应用时仍保留原有行为；经过 Nginx 反向代理时，交给 Nginx 直接发送文件。
    if not request.headers.get("x-forwarded-for"):
        return FileResponse(path, filename=download_name)

    try:
        relative_path = path.resolve().relative_to(config.report_dir.resolve())
    except ValueError:
        return FileResponse(path, filename=download_name)

    quoted_segments = [quote(part) for part in relative_path.parts]
    accel_path = "/_protected-reports/" + "/".join(quoted_segments)
    response = Response()
    response.headers["X-Accel-Redirect"] = accel_path
    response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(download_name)}"
    media_type = mimetypes.guess_type(download_name)[0] or "application/octet-stream"
    response.headers["Content-Type"] = media_type
    # 上游响应没有正文，文件由 X-Accel-Redirect 触发的 Nginx internal location
    # 发送。不能把文件大小声明成上游正文长度，否则 Uvicorn 会因实际发送 0
    # 字节而抛出 "Response content shorter than Content-Length"。
    del response.headers["Content-Length"]
    return response
