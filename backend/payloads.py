"""请求体解析。

裸 `await request.json()` 在请求体不是合法 JSON 时会抛 JSONDecodeError 或
UnicodeDecodeError（例如误把 multipart 发到 JSON 端点），未捕获就是 500。
客户端发错东西应该得到 400。
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request


async def read_json(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="请求体不是合法的 JSON") from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="请求体应为 JSON 对象")
    return payload
