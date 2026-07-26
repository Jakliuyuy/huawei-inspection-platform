"""本地模式：免登录、单用户、鉴权在唯一分支点上放行。

与 test_api_smoke 分开是因为 server 在导入时读环境变量，两种模式
必须各自导入一次模块。
"""

from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def local_client():
    tmp_root = Path(tempfile.mkdtemp(prefix="local-data-"))
    saved_env = dict(os.environ)
    saved_server = sys.modules.pop("server", None)
    # backend.config 在导入时读 LOCAL_MODE，必须一并卸载
    for name in [key for key in sys.modules if key.startswith("backend")]:
        sys.modules.pop(name, None)

    os.environ.update(DATA_ROOT=str(tmp_root), LOCAL_MODE="true", MAX_JOB_WORKERS="1")
    os.environ.pop("SECURE_COOKIES", None)
    sys.path.insert(0, str(REPO_ROOT))
    try:
        import server
        from fastapi.testclient import TestClient

        with TestClient(server.app) as client:
            yield client, server
    finally:
        for name in [key for key in sys.modules if key.startswith("backend")]:
            sys.modules.pop(name, None)
        sys.modules.pop("server", None)
        if saved_server is not None:
            sys.modules["server"] = saved_server
        os.environ.clear()
        os.environ.update(saved_env)
        shutil.rmtree(tmp_root, ignore_errors=True)


def test_no_login_required(local_client):
    client, _ = local_client
    body = client.get("/api/auth/me").json()
    assert body["auth_mode"] == "local"
    assert body["is_admin"] is True


def test_protected_endpoints_open_without_cookie(local_client):
    client, _ = local_client
    client.cookies.clear()
    for path in ("/api/jobs", "/api/announcements", "/api/systems", "/api/admin/users"):
        assert client.get(path).status_code == 200, f"{path} 在本地模式下应放行"


def test_secure_cookie_defaults_off_locally(local_client):
    """localhost 走 http，Secure Cookie 会被丢弃，本地模式必须默认关闭。"""
    _, server = local_client
    assert server.config.secure_cookies is False
    assert server.config.local_mode is True


def test_local_user_row_exists(local_client):
    """必须是真实数据库行 —— jobs.user_id 有外键约束。"""
    _, server = local_client
    from backend.auth import local_user

    user = local_user()
    assert user is not None and user["is_admin"] == 1


def test_upload_and_create_job_works_without_login(local_client):
    client, _ = local_client
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("2026-07-24/TOC/TOC_JZ-TOC-EOR01BHW_10.0.0.1.log", "<JZ-TOC-EOR01BHW>display version\n")

    preview = client.post("/api/uploads", files={"files": ("logs.zip", buf.getvalue(), "application/zip")})
    assert preview.status_code == 200, preview.text

    created = client.post(
        "/api/jobs",
        json={"upload_id": preview.json()["upload_id"], "systems": ["TOC"], "report_date": "2026-07-24"},
    )
    assert created.status_code == 200, created.text
