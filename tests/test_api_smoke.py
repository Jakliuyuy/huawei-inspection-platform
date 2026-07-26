"""API 冒烟：端点存在性、鉴权边界、响应契约。

目的不是覆盖业务逻辑，而是在拆分 server.py 的几十个提交里，
自动发现"路由搬丢了"和"响应字段改了"——1494 行里 30 个端点靠人眼数不现实。

注意：server.py 在**模块导入时**执行 build_config()，所以环境变量必须
在 import server 之前设好。整个模块共用一个临时 DATA_ROOT，绝不碰真实数据。

SMTP 相关环境变量一律不设 —— 发信端点会直接返回 400，
测试在物理上不可能把邮件发出去。
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

ADMIN_USER = "smoke-admin"
ADMIN_PASS = "smoke-password-123456"


@pytest.fixture(scope="module")
def app_module():
    """在隔离的 DATA_ROOT 下导入 server，并跑完 startup。"""
    tmp_root = Path(tempfile.mkdtemp(prefix="smoke-data-"))
    saved_env = dict(os.environ)
    saved_server = sys.modules.pop("server", None)

    os.environ.update(
        DATA_ROOT=str(tmp_root),
        SECURE_COOKIES="false",
        DEFAULT_ADMIN_USERNAME=ADMIN_USER,
        DEFAULT_ADMIN_PASSWORD=ADMIN_PASS,
        MAX_JOB_WORKERS="1",  # 走串行分支，避免测试里起进程池
        RETENTION_DAYS="30",
    )
    # SMTP_* 一律不设：发信端点直接 400，测试不可能真发邮件
    for key in ("SMTP_USERNAME", "SMTP_PASSWORD"):
        os.environ.pop(key, None)

    sys.path.insert(0, str(REPO_ROOT))
    try:
        import server  # noqa: PLC0415

        yield server
    finally:
        sys.modules.pop("server", None)
        if saved_server is not None:
            sys.modules["server"] = saved_server
        os.environ.clear()
        os.environ.update(saved_env)
        shutil.rmtree(tmp_root, ignore_errors=True)


@pytest.fixture(scope="module")
def client(app_module):
    from fastapi.testclient import TestClient

    with TestClient(app_module.app) as c:  # with 触发 startup
        yield c


@pytest.fixture(scope="module")
def admin(client):
    r = client.post("/api/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert r.status_code == 200, r.text
    return client


def _tiny_log_zip() -> bytes:
    """一个最小的合法上传：单系统单设备。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "2026-07-24/TOC/TOC_JZ-TOC-EOR01BHW_10.0.0.1.log",
            "<JZ-TOC-EOR01BHW>display version\nHuawei Versatile Routing Platform\n",
        )
    return buf.getvalue()


# ---------------------------------------------------------------- 鉴权边界


def test_health_is_public(client):
    assert client.get("/api/health").status_code == 200


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/auth/me"),
        ("get", "/api/announcements"),  # 曾经完全无鉴权，已修
        ("get", "/api/jobs"),
        ("get", "/api/email-config"),
        ("get", "/api/admin/users"),
        ("get", "/api/admin/jobs"),
        ("get", "/api/admin/audits"),
        ("get", "/api/admin/reports/dates"),
    ],
)
def test_endpoints_require_auth(client, method, path):
    client.cookies.clear()
    assert getattr(client, method)(path).status_code == 401, f"{path} 未要求登录"


def test_login_rejects_bad_password(client):
    client.cookies.clear()
    r = client.post("/api/auth/login", json={"username": ADMIN_USER, "password": "wrong"})
    assert r.status_code == 401


def test_login_sets_session_and_me_works(admin):
    r = admin.get("/api/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == ADMIN_USER
    assert body["is_admin"] is True


# ---------------------------------------------------------------- 响应契约


def test_me_contract(admin):
    assert set(admin.get("/api/auth/me").json()) >= {
        "id", "username", "is_admin", "role_label", "created_at", "last_login_at",
    }


def test_jobs_page_contract(admin):
    body = admin.get("/api/jobs").json()
    assert set(body) >= {"items", "page", "page_size", "total", "total_pages", "stats"}
    assert set(body["stats"]) >= {"total", "active", "completed", "failed"}


def test_announcement_contract(admin):
    assert "content" in admin.get("/api/announcements").json()


def test_admin_listing_contracts(admin):
    assert isinstance(admin.get("/api/admin/users").json(), list)
    assert set(admin.get("/api/admin/audits").json()) >= {
        "items", "page", "page_size", "total", "total_pages",
    }
    assert isinstance(admin.get("/api/admin/reports/dates").json(), list)


# ---------------------------------------------------------------- 任务生命周期


@pytest.fixture(scope="module")
def plain_user(admin, client):
    """一个非管理员账号，登录后的独立 client。"""
    admin.post(
        "/api/admin/users",
        json={"username": "plain-user", "password": "plain-password-1", "is_admin": False},
    )  # 已存在时返回 400，无妨
    other = type(client)(client.app)
    assert other.post(
        "/api/auth/login", json={"username": "plain-user", "password": "plain-password-1"}
    ).status_code == 200
    return other


def _make_upload(cli) -> dict:
    r = cli.post("/api/uploads", files={"files": ("logs.zip", _tiny_log_zip(), "application/zip")})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def upload_preview(admin) -> dict:
    """给只读用例共用的一份上传；不要用它建任务（建任务会消费掉它）。"""
    return _make_upload(admin)


@pytest.fixture
def fresh_upload(admin) -> dict:
    """每个用例独享一份，供会消费 upload_id 的校验用例使用。"""
    return _make_upload(admin)


def test_upload_preview_contract(upload_preview):
    assert set(upload_preview) >= {
        "upload_id", "log_root_label", "detected", "log_file_count",
        "suggested_report_date", "systems",
    }
    by_key = {s["key"]: s for s in upload_preview["systems"]}
    assert set(by_key) == {"TOC", "TOB", "GPRS", "Softswitch", "SMS", "IntelligentNet", "NM1", "NM2", "NM3"}
    assert set(by_key["TOC"]) >= {
        "key", "display_name", "expected", "actual", "missing", "has_logs", "output_name_template",
    }
    # zip 里只放了一个 TOC 日志
    assert by_key["TOC"]["actual"] == 1 and by_key["TOC"]["has_logs"] is True
    assert by_key["GPRS"]["actual"] == 0 and by_key["GPRS"]["has_logs"] is False


def test_upload_preview_is_refetchable(admin, upload_preview):
    r = admin.get(f"/api/uploads/{upload_preview['upload_id']}")
    assert r.status_code == 200
    assert r.json()["upload_id"] == upload_preview["upload_id"]


def test_upload_is_owner_scoped(plain_user, upload_preview):
    assert plain_user.get(f"/api/uploads/{upload_preview['upload_id']}").status_code == 404


def test_systems_listing(admin):
    body = admin.get("/api/systems").json()
    assert len(body["systems"]) == 9
    assert set(body["systems"][0]) >= {"key", "display_name", "host_count", "output_name_template"}


@pytest.fixture(scope="module")
def created_job(admin) -> str:
    own = _make_upload(admin)
    r = admin.post(
        "/api/jobs",
        json={
            "upload_id": own["upload_id"],
            "systems": ["TOC"],
            "report_date": "2026-07-24",
        },
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    assert job_id
    return job_id


def test_create_job_records_scope_and_date(admin, created_job):
    body = admin.get(f"/api/jobs/{created_job}").json()
    assert body["report_date"] == "2026-07-24"
    assert body["selected_systems"] == ["TOC"]


def test_create_job_rejects_unknown_system(admin, fresh_upload):
    r = admin.post(
        "/api/jobs",
        json={"upload_id": fresh_upload["upload_id"], "systems": ["NoSuchSystem"]},
    )
    assert r.status_code == 400 and "NoSuchSystem" in r.json()["detail"]


def test_create_job_rejects_bad_date(admin, fresh_upload):
    r = admin.post(
        "/api/jobs",
        json={"upload_id": fresh_upload["upload_id"], "report_date": "2026/07/24"},
    )
    assert r.status_code == 400


def test_create_job_rejects_unknown_upload(admin):
    r = admin.post("/api/jobs", json={"upload_id": "u-does-not-exist"})
    assert r.status_code == 404


def test_json_endpoints_reject_malformed_body(admin):
    """非法请求体应得到 400，而不是未捕获异常导致的 500。"""
    r = admin.post("/api/jobs", content=b"\xfb\xfc not json", headers={"content-type": "application/json"})
    assert r.status_code == 400


def test_job_detail_contract(admin, created_job):
    body = admin.get(f"/api/jobs/{created_job}").json()
    assert set(body) >= {
        "id", "status", "status_label", "progress", "status_detail",
        "created_at", "username", "generated_files", "timeline",
        "bundle_available", "error_message",
    }
    assert body["id"] == created_job


def test_job_appears_in_listing(admin, created_job):
    ids = [j["id"] for j in admin.get("/api/jobs").json()["items"]]
    assert created_job in ids


def test_unknown_job_is_404(admin):
    assert admin.get("/api/jobs/does-not-exist").status_code == 404


# ---------------------------------------------------------------- 越权


def test_non_admin_cannot_reach_admin_endpoints(plain_user):
    for path in ("/api/admin/users", "/api/admin/jobs", "/api/admin/audits"):
        assert plain_user.get(path).status_code == 403, f"{path} 未拦截非管理员"


def test_non_owner_cannot_read_others_job(plain_user, created_job):
    assert plain_user.get(f"/api/jobs/{created_job}").status_code == 403


# ---------------------------------------------------------------- 发信安全


def test_send_email_blocked_without_smtp_config(admin, created_job):
    """SMTP 未配置时必须直接 400——这是自动化测试永不发信的保险丝。"""
    r = admin.post(
        f"/api/jobs/{created_job}/send-email",
        json={"files": [{"name": "x.docx", "recipients": ["a@example.com"]}]},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------- 路径穿越


@pytest.mark.parametrize(
    "payload",
    [
        "../../runtime/app.db",
        "../../../.env",
        "/app/.env",
        "C:/Windows/win.ini",
        "..\\..\\runtime\\app.db",
        "....//....//runtime/app.db",
        "%2e%2e%2fapp.db",
        "report.docx.zip",  # 非 .docx 后缀
        "not-in-whitelist.docx",  # 后缀对但不在 generated_files 里
    ],
)
def test_report_path_resolution_rejects_traversal(app_module, payload):
    """锁住已修复的任意文件读取漏洞（发邮件附件路径）。"""
    import json as _json

    from fastapi import HTTPException

    from backend.paths import resolve_job_report_path

    job = {
        "output_path": str(REPO_ROOT / "data" / "reports" / "20260727-001"),
        "generated_files": _json.dumps(["TOC2026-07-24日巡检报告.docx"]),
    }
    with pytest.raises(HTTPException) as exc:
        resolve_job_report_path(job, payload)
    assert exc.value.status_code in (400, 403)


@pytest.mark.parametrize(
    "payload,expected",
    [
        ("../../runtime/app.db", "app.db"),  # 目录成分被剥掉，落回 base 内
        ("/etc/passwd", "passwd"),
        ("a/../../../x", "x"),
        ("report.docx", "report.docx"),
    ],
)
def test_resolve_within_strips_directory_components(payload, expected):
    from backend.paths import resolve_within

    got = resolve_within(Path("data/reports/20260727-001"), payload)
    assert got is not None and got.name == expected


@pytest.mark.parametrize("payload", ["..", "", "."])
def test_resolve_within_rejects_non_files(payload):
    from backend.paths import resolve_within

    assert resolve_within(Path("data/reports/20260727-001"), payload) is None


def test_report_path_resolution_accepts_whitelisted_name(app_module):
    import json as _json

    from backend.paths import resolve_job_report_path

    name = "TOC2026-07-24日巡检报告.docx"
    job = {
        "output_path": str(REPO_ROOT / "data" / "reports" / "20260727-001"),
        "generated_files": _json.dumps([name]),
    }
    assert resolve_job_report_path(job, name).name == name
