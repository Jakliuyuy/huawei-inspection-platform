"""密码哈希、令牌哈希与客户端 IP 解析。"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from fastapi import Request

PBKDF2_ITERATIONS = 120_000


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    salt, _, _ = encoded.partition("$")
    candidate = hash_password(password, salt)
    return hmac.compare_digest(candidate, encoded)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def client_ip(request: Request | None) -> str:
    """取真实客户端 IP。

    容器前面是 Nginx + docker-proxy，直连对端是网桥网关，所以必须读
    X-Forwarded-For 首段。这要求 uvicorn 以 --proxy-headers 启动
    （见 Dockerfile），否则该头可被客户端伪造。
    """
    if request is None:
        return ""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else ""
