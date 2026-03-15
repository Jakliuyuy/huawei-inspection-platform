from __future__ import annotations

from typing import Any, Mapping

from fastapi.responses import HTMLResponse

UserLike = Mapping[str, Any]

BASE_STYLES = """
        <style>
            :root {
                --bg: #e9edf3;
                --bg-deep: #0f172a;
                --card: rgba(255, 255, 255, 0.9);
                --card-strong: #ffffff;
                --ink: #162033;
                --ink-soft: #42506a;
                --accent: #0f766e;
                --accent-strong: #115e59;
                --accent-warm: #f59e0b;
                --line: rgba(148, 163, 184, 0.22);
                --line-strong: rgba(15, 23, 42, 0.12);
                --muted: #64748b;
                --danger: #b91c1c;
                --shadow: 0 24px 60px rgba(15, 23, 42, 0.12);
            }
            * { box-sizing: border-box; }
            body {
                margin: 0;
                font-family: "PingFang SC", "Noto Sans SC", "Microsoft YaHei", sans-serif;
                color: var(--ink);
                background:
                    radial-gradient(circle at 12% 18%, rgba(15, 118, 110, 0.22), transparent 22%),
                    radial-gradient(circle at 88% 10%, rgba(245, 158, 11, 0.18), transparent 18%),
                    radial-gradient(circle at 50% 100%, rgba(30, 41, 59, 0.16), transparent 26%),
                    linear-gradient(180deg, #f7fafc, var(--bg));
                min-height: 100vh;
            }
            .shell { max-width: 1240px; margin: 0 auto; padding: 18px; }
            .hero {
                position: relative;
                overflow: hidden;
                background:
                    radial-gradient(circle at top right, rgba(255,255,255,0.16), transparent 28%),
                    linear-gradient(135deg, #0f172a 0%, #12324a 45%, #115e59 100%);
                color: #fff;
                border-radius: 22px;
                padding: 20px 24px;
                box-shadow: 0 18px 34px rgba(15, 23, 42, 0.24);
            }
            .hero::after {
                content: "";
                position: absolute;
                inset: auto -8% -32% auto;
                width: 340px;
                height: 340px;
                border-radius: 50%;
                background: radial-gradient(circle, rgba(245, 158, 11, 0.35), transparent 70%);
            }
            .hero h1 {
                position: relative;
                margin: 0 0 6px;
                font-size: clamp(24px, 4vw, 36px);
                letter-spacing: 0.04em;
            }
            .hero p {
                position: relative;
                margin: 0;
                max-width: 760px;
                color: rgba(255,255,255,0.8);
                font-size: 14px;
                line-height: 1.55;
            }
            .nav {
                display: flex;
                justify-content: space-between;
                gap: 12px;
                align-items: center;
                margin: 14px 0 0;
                flex-wrap: wrap;
                padding: 12px 14px;
                border-radius: 18px;
                background: rgba(255,255,255,0.72);
                backdrop-filter: blur(18px);
                border: 1px solid rgba(255,255,255,0.6);
                box-shadow: 0 12px 26px rgba(15, 23, 42, 0.08);
            }
            .nav-brand {
                display: flex;
                flex-direction: column;
                gap: 4px;
            }
            .nav-kicker {
                font-size: 11px;
                letter-spacing: 0.18em;
                text-transform: uppercase;
                color: var(--muted);
            }
            .nav-links {
                display: flex;
                gap: 12px;
                align-items: center;
                flex-wrap: wrap;
            }
            .nav a, .nav button {
                text-decoration: none;
                color: var(--ink);
                background: rgba(255,255,255,0.85);
                border: 1px solid rgba(148, 163, 184, 0.24);
                border-radius: 999px;
                padding: 8px 14px;
                cursor: pointer;
                font-weight: 700;
            }
            .nav form { margin: 0; }
            .grid { display: grid; gap: 16px; margin-top: 16px; }
            .grid.two { grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
            .card {
                background: var(--card);
                backdrop-filter: blur(16px);
                border: 1px solid rgba(255,255,255,0.7);
                border-radius: 20px;
                padding: 18px;
                box-shadow: var(--shadow);
            }
            .card h2 {
                margin: 0 0 10px;
                font-size: 20px;
                letter-spacing: -0.02em;
            }
            .card h3 { margin: 14px 0 8px; }
            .card p, .card li { line-height: 1.55; color: var(--ink-soft); }
            .panel-title {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                margin-bottom: 10px;
            }
            .eyebrow {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 6px 10px;
                border-radius: 999px;
                background: rgba(15, 118, 110, 0.1);
                color: var(--accent);
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }
            label { display: block; margin-bottom: 8px; font-weight: 700; color: var(--ink); }
            input, textarea, select {
                width: 100%;
                padding: 14px 16px;
                border-radius: 16px;
                border: 1px solid rgba(148, 163, 184, 0.25);
                background: rgba(255,255,255,0.9);
                margin-bottom: 14px;
                font-size: 15px;
                color: var(--ink);
            }
            input:focus, textarea:focus, select:focus {
                outline: none;
                border-color: rgba(15, 118, 110, 0.55);
                box-shadow: 0 0 0 4px rgba(15, 118, 110, 0.12);
            }
            button, .button {
                display: inline-block;
                background: linear-gradient(135deg, var(--accent), var(--accent-strong));
                color: #fff;
                border: none;
                border-radius: 16px;
                padding: 10px 15px;
                cursor: pointer;
                text-decoration: none;
                font-weight: 800;
                letter-spacing: 0.02em;
                box-shadow: 0 10px 18px rgba(15, 118, 110, 0.18);
            }
            .button.secondary {
                background: rgba(255,255,255,0.72);
                color: var(--accent-strong);
                border: 1px solid rgba(15, 118, 110, 0.18);
                box-shadow: none;
            }
            .stats {
                display: grid;
                gap: 10px;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            }
            .stat {
                padding: 12px;
                border-radius: 16px;
                background: linear-gradient(180deg, rgba(255,255,255,0.94), rgba(241,245,249,0.9));
                border: 1px solid rgba(148, 163, 184, 0.16);
            }
            .stat strong {
                display: block;
                margin-top: 5px;
                font-size: 22px;
                line-height: 1;
                color: var(--ink);
            }
            .stat span { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; }
            .table-wrap { overflow-x: auto; }
            table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 14px; }
            th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid rgba(148, 163, 184, 0.16); vertical-align: top; }
            th {
                font-size: 12px;
                color: var(--muted);
                text-transform: uppercase;
                letter-spacing: 0.08em;
            }
            tr:hover td { background: rgba(255,255,255,0.46); }
            .tag {
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 0.04em;
                background: rgba(245, 158, 11, 0.14);
                color: #9a3412;
            }
            .tag.done { background: #dcfce7; color: #166534; }
            .tag.fail { background: #fee2e2; color: #991b1b; }
            .tag.wait { background: #fffbeb; color: #92400e; }
            .progress {
                width: 100%;
                height: 12px;
                background: rgba(203, 213, 225, 0.45);
                border-radius: 999px;
                overflow: hidden;
                border: 1px solid rgba(148, 163, 184, 0.12);
            }
            .progress > span {
                display: block;
                height: 100%;
                background: linear-gradient(90deg, var(--accent), var(--accent-warm));
                border-radius: 999px;
                transition: width 0.3s ease;
            }
            .progress-meta {
                display: flex;
                justify-content: space-between;
                gap: 12px;
                margin-top: 8px;
                font-size: 13px;
                color: var(--muted);
            }
            .list-clean {
                list-style: none;
                margin: 0;
                padding: 0;
            }
            .list-clean li {
                padding: 12px 0;
                border-bottom: 1px solid rgba(148, 163, 184, 0.16);
            }
            .list-clean li:last-child { border-bottom: none; }
            .dropzone {
                position: relative;
                padding: 18px;
                border-radius: 18px;
                border: 2px dashed rgba(15, 118, 110, 0.28);
                background:
                    linear-gradient(180deg, rgba(255,255,255,0.9), rgba(240,253,250,0.88));
                transition: 0.2s ease;
                text-align: center;
                margin-bottom: 12px;
            }
            .dropzone.dragover {
                transform: translateY(-2px);
                border-color: rgba(15, 118, 110, 0.7);
                box-shadow: 0 18px 36px rgba(15, 118, 110, 0.12);
            }
            .dropzone strong {
                display: block;
                font-size: 18px;
                margin-bottom: 6px;
            }
            .dropzone p {
                margin: 0;
            }
            .file-summary {
                margin-top: 10px;
                padding: 12px 14px;
                border-radius: 14px;
                background: rgba(255,255,255,0.78);
                border: 1px solid rgba(148, 163, 184, 0.16);
            }
            .file-summary strong {
                display: block;
                margin-bottom: 6px;
            }
            .upload-layout {
                display: grid;
                grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.8fr);
                gap: 16px;
                align-items: start;
            }
            .upload-side {
                display: grid;
                gap: 16px;
            }
            .hint-box {
                padding: 14px;
                border-radius: 16px;
                background: rgba(255,255,255,0.72);
                border: 1px solid rgba(148, 163, 184, 0.16);
            }
            .timeline {
                list-style: none;
                margin: 0;
                padding: 0;
                display: grid;
                gap: 14px;
            }
            .timeline-item {
                display: grid;
                grid-template-columns: 40px 1fr;
                gap: 14px;
                align-items: start;
                padding: 14px 16px;
                border-radius: 18px;
                border: 1px solid rgba(148, 163, 184, 0.16);
                background: rgba(255,255,255,0.68);
            }
            .timeline-dot {
                display: inline-flex;
                width: 32px;
                height: 32px;
                align-items: center;
                justify-content: center;
                border-radius: 50%;
                font-size: 12px;
                font-weight: 800;
                color: #fff;
                background: rgba(148, 163, 184, 0.7);
            }
            .timeline-item.done .timeline-dot {
                background: linear-gradient(135deg, var(--accent), var(--accent-warm));
            }
            .timeline-item strong {
                display: block;
                margin-bottom: 4px;
            }
            .timeline-item p {
                margin: 0;
                font-size: 14px;
            }
            .data-pair {
                display: grid;
                grid-template-columns: 120px 1fr;
                gap: 10px;
                padding: 10px 0;
                border-bottom: 1px solid rgba(148, 163, 184, 0.14);
            }
            .data-pair:last-child { border-bottom: none; }
            .data-pair strong { color: var(--ink); }
            .inline-actions {
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
            }
            .inline-actions form { margin: 0; }
            .button.danger, button.danger {
                background: rgba(255,255,255,0.72);
                color: var(--accent-strong);
                border: 1px solid rgba(15, 118, 110, 0.18);
                box-shadow: none;
            }
            .subnav {
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
                margin-bottom: 12px;
            }
            .subnav a {
                display: inline-flex;
                align-items: center;
                padding: 8px 14px;
                border-radius: 999px;
                background: rgba(255,255,255,0.78);
                border: 1px solid rgba(148, 163, 184, 0.18);
                text-decoration: none;
                color: var(--ink);
                font-weight: 700;
            }
            .subnav a.active {
                background: linear-gradient(135deg, var(--accent), var(--accent-strong));
                color: #fff;
                border-color: transparent;
            }
            .crumbs {
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
                margin-bottom: 12px;
                font-size: 13px;
                color: var(--muted);
            }
            .crumbs a {
                text-decoration: none;
                color: var(--accent-strong);
                font-weight: 700;
            }
            .toolbar {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 12px;
                margin-bottom: 12px;
                flex-wrap: wrap;
            }
            .modal {
                position: fixed;
                inset: 0;
                display: none;
                align-items: center;
                justify-content: center;
                padding: 20px;
                background: rgba(15, 23, 42, 0.45);
                z-index: 1000;
            }
            .modal.open { display: flex; }
            .modal-panel {
                width: min(520px, 100%);
                background: rgba(255,255,255,0.98);
                border-radius: 20px;
                padding: 20px;
                box-shadow: 0 24px 60px rgba(15, 23, 42, 0.22);
                border: 1px solid rgba(148, 163, 184, 0.18);
            }
            .modal-close {
                background: rgba(255,255,255,0.72);
                color: var(--accent-strong);
                border: 1px solid rgba(15, 118, 110, 0.18);
                box-shadow: none;
            }
            .stack {
                display: grid;
                gap: 12px;
            }
            a { color: var(--accent-strong); }
            .muted { color: var(--muted); }
            .danger { color: var(--danger); }
            @media (max-width: 768px) {
                .shell { padding: 16px; }
                .hero { padding: 24px; border-radius: 24px; }
                .nav { padding: 14px; }
                .nav-links { width: 100%; }
                .nav-links a, .nav-links form, .nav-links button {
                    width: 100%;
                }
                .data-pair {
                    grid-template-columns: 1fr;
                    gap: 4px;
                }
                .upload-layout {
                    grid-template-columns: 1fr;
                }
            }
        </style>
"""


def render_page(title: str, body: str, user: UserLike | None = None) -> HTMLResponse:
    nav = ""
    if user:
        nav = f"""
        <nav class="nav">
            <div class="nav-brand">
                <span class="nav-kicker">Inspection Cloud</span>
                <strong>当前用户：{user['username']}</strong>
            </div>
            <div class="nav-links">
                <a href="/dashboard">任务中心</a>
                <a href="/upload">新建任务</a>
                <a href="/admin">系统管理</a>
                <form action="/logout" method="post"><button type="submit">退出登录</button></form>
            </div>
        </nav>
        """
    html = f"""
    <html lang="zh-CN">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{title}</title>
        {BASE_STYLES}
    </head>
    <body>
        <div class="shell">
            <section class="hero">
                <h1>华为巡检云平台</h1>
                <p>上传日志，云端生成巡检报告，统一管理账号、审计和下载。</p>
            </section>
            {nav}
            {body}
        </div>
    </body>
    </html>
    """
    return HTMLResponse(html)


def render_progress(progress: int, detail: str | None = None) -> str:
    safe_progress = max(0, min(100, int(progress)))
    detail_text = detail or "等待处理"
    return f"""
    <div class="progress"><span style="width: {safe_progress}%;"></span></div>
    <div class="progress-meta"><span>{safe_progress}%</span><span>{detail_text}</span></div>
    """


def render_home_page(app_title: str, announcement: str) -> HTMLResponse:
    body = f"""
    <div class="grid two">
        <div class="card">
            <div class="panel-title">
                <h2>登录平台</h2>
                <span class="eyebrow">Secure Access</span>
            </div>
            <p class="muted">用于上传巡检日志、跟踪生成进度、下载报告和查看审计记录。</p>
            <form action="/login" method="post">
                <label>用户名</label>
                <input name="username" required>
                <label>密码</label>
                <input name="password" type="password" required>
                <button type="submit">登录平台</button>
            </form>
        </div>
        <div class="card">
            <div class="panel-title">
                <h2>平台概览</h2>
                <span class="eyebrow">Live</span>
            </div>
            <p>{announcement}</p>
            <div class="stats">
                <div class="stat"><span>上传格式</span><strong>ZIP / 文件夹</strong></div>
                <div class="stat"><span>报告输出</span><strong>Word</strong></div>
                <div class="stat"><span>运行模式</span><strong>Docker</strong></div>
            </div>
            <h3>当前能力</h3>
            <ul class="list-clean">
                <li>支持上传 ZIP 或多份日志文件</li>
                <li>云端自动生成 Word 巡检报告</li>
                <li>统一任务、下载、公告和审计管理</li>
            </ul>
        </div>
    </div>
    """
    return render_page(app_title, body)


def render_dashboard_page(
    user: UserLike,
    rows_html: str,
    total_jobs: int,
    active_jobs: int,
    completed_jobs: int,
    failed_jobs: int,
    announcement: str,
) -> HTMLResponse:
    refresh = "<script>setTimeout(function(){ window.location.reload(); }, 5000);</script>" if active_jobs else ""
    body = f"""
    {refresh}
    <div class="grid two">
        <div class="card">
            <div class="panel-title">
                <h2>任务态势</h2>
                <span class="eyebrow">Realtime</span>
            </div>
            <div class="stats">
                <div class="stat"><span>总任务数</span><strong>{total_jobs}</strong></div>
                <div class="stat"><span>处理中</span><strong>{active_jobs}</strong></div>
                <div class="stat"><span>已完成</span><strong>{completed_jobs}</strong></div>
                <div class="stat"><span>失败</span><strong>{failed_jobs}</strong></div>
            </div>
        </div>
        <div class="card">
            <div class="panel-title">
                <h2>系统公告</h2>
                <span class="eyebrow">Notice</span>
            </div>
            <p>{announcement}</p>
            <a class="button" href="/upload">创建新任务</a>
        </div>
    </div>
    <div class="card">
        <div class="panel-title">
            <h2>任务中心</h2>
            <span class="eyebrow">Auto Refresh {('On' if active_jobs else 'Off')}</span>
        </div>
        <div class="table-wrap">
            <table>
                <thead>
                    <tr><th>任务ID</th><th>提交人</th><th>状态</th><th>进度</th><th>创建时间</th><th>完成时间</th><th>操作</th></tr>
                </thead>
                <tbody>
                    {rows_html or '<tr><td colspan="7">当前还没有任务记录，先去创建一个上传任务。</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>
    """
    return render_page("任务列表", body, user)


def render_upload_page(user: UserLike) -> HTMLResponse:
    body = """
    <div class="upload-layout">
        <div class="card">
            <div class="panel-title">
                <h2>创建巡检任务</h2>
                <span class="eyebrow">Upload</span>
            </div>
            <p class="muted">支持 ZIP 压缩包和整个日志目录。后端会保留原始层级，并自动识别类似 `2026-3-13/TOC/...` 的结构。</p>
            <form action="/jobs" method="post" enctype="multipart/form-data">
                <div class="dropzone" id="dropzone">
                    <strong>拖拽 ZIP 或日志文件夹到这里</strong>
                    <p class="muted">也可以继续使用下面的文件选择器。</p>
                    <div class="file-summary" id="fileSummary">
                        <strong>当前未选择文件</strong>
                        <span class="muted">等待上传内容</span>
                    </div>
                </div>
                <label>ZIP 压缩包或日志文件</label>
                <input id="filesInput" name="files" type="file" accept=".zip,.log,application/zip" multiple>
                <label>日志文件夹</label>
                <input id="folderInput" name="files" type="file" webkitdirectory directory>
                <button type="submit">提交任务</button>
            </form>
        </div>
        <div class="upload-side">
            <div class="card hint-box">
                <div class="panel-title">
                    <h2>推荐方式</h2>
                    <span class="eyebrow">Best</span>
                </div>
                <ul class="list-clean">
                    <li>优先上传完整日志目录。</li>
                    <li>压缩包建议保留日期和系统子目录。</li>
                    <li>避免混入无关日志。</li>
                </ul>
            </div>
            <div class="card hint-box">
                <div class="panel-title">
                    <h2>处理流程</h2>
                    <span class="eyebrow">Flow</span>
                </div>
                <ul class="list-clean">
                    <li>上传进入排队。</li>
                    <li>识别日志根目录。</li>
                    <li>生成 Word 报告。</li>
                    <li>自动打包下载。</li>
                </ul>
            </div>
        </div>
    </div>
    <script>
    (function () {
        const dropzone = document.getElementById("dropzone");
        const filesInput = document.getElementById("filesInput");
        const folderInput = document.getElementById("folderInput");
        const fileSummary = document.getElementById("fileSummary");

        function updateSummary() {
            const files = [...(filesInput.files || []), ...(folderInput.files || [])];
            if (!files.length) {
                fileSummary.innerHTML = "<strong>当前未选择文件</strong><span class='muted'>等待上传内容</span>";
                return;
            }
            const names = files.slice(0, 6).map(file => file.webkitRelativePath || file.name);
            const more = files.length > 6 ? "<li>... 还有 " + (files.length - 6) + " 个文件</li>" : "";
            fileSummary.innerHTML =
                "<strong>已选择 " + files.length + " 个文件</strong>" +
                "<ul class='list-clean'>" + names.map(name => "<li>" + name + "</li>").join("") + more + "</ul>";
        }

        filesInput.addEventListener("change", updateSummary);
        folderInput.addEventListener("change", updateSummary);

        ["dragenter", "dragover"].forEach(eventName => {
            dropzone.addEventListener(eventName, function (event) {
                event.preventDefault();
                dropzone.classList.add("dragover");
            });
        });
        ["dragleave", "drop"].forEach(eventName => {
            dropzone.addEventListener(eventName, function (event) {
                event.preventDefault();
                dropzone.classList.remove("dragover");
            });
        });
        dropzone.addEventListener("drop", function (event) {
            const files = event.dataTransfer.files;
            if (!files || !files.length) {
                return;
            }
            filesInput.files = files;
            updateSummary();
        });
    })();
    </script>
    """
    return render_page("创建任务", body, user)


def render_job_detail_page(
    user: UserLike,
    job_id: str,
    username: str,
    status_html: str,
    progress_html: str,
    created_at: str,
    finished_at: str,
    log_root: str,
    download_html: str,
    file_links_html: str,
    error_message: str,
    timeline_html: str,
    auto_refresh: bool,
) -> HTMLResponse:
    refresh = "<script>setTimeout(function(){ window.location.reload(); }, 3000);</script>" if auto_refresh else ""
    body = f"""
    {refresh}
    <div class="grid two">
        <div class="card">
            <div class="panel-title">
                <h2>任务状态</h2>
                <span class="eyebrow">Job Detail</span>
            </div>
            <div class="data-pair"><strong>任务ID</strong><span>{job_id}</span></div>
            <div class="data-pair"><strong>提交人</strong><span>{username}</span></div>
            <div class="data-pair"><strong>当前状态</strong><span>{status_html}</span></div>
            {progress_html}
            <div class="data-pair"><strong>创建时间</strong><span>{created_at}</span></div>
            <div class="data-pair"><strong>完成时间</strong><span>{finished_at}</span></div>
            <div class="data-pair"><strong>日志根目录</strong><span>{log_root}</span></div>
            {download_html}
        </div>
        <div class="card">
            <div class="panel-title">
                <h2>结果文件</h2>
                <span class="eyebrow">Outputs</span>
            </div>
            <ul class="list-clean">{file_links_html or '<li>尚未生成文件</li>'}</ul>
            <h3>错误信息</h3>
            <p class="danger">{error_message}</p>
        </div>
    </div>
    <div class="card">
        <div class="panel-title">
            <h2>处理时间线</h2>
            <span class="eyebrow">Timeline</span>
        </div>
        {timeline_html}
    </div>
    """
    return render_page(f"任务 {job_id}", body, user)


def render_admin_page(user: UserLike, section_nav: str, section_body: str) -> HTMLResponse:
    body = f"""
    {section_nav}
    {section_body}
    <script>
    function openModal(id) {{
        const element = document.getElementById(id);
        if (element) element.classList.add('open');
    }}
    function closeModal(id) {{
        const element = document.getElementById(id);
        if (element) element.classList.remove('open');
    }}
    function closeModalOnBackdrop(event, id) {{
        if (event.target && event.target.id === id) closeModal(id);
    }}
    </script>
    """
    return render_page("管理后台", body, user)


def render_error_page(detail: str) -> HTMLResponse:
    body = f"""
    <div class="card">
        <div class="panel-title">
            <h2>请求失败</h2>
            <span class="eyebrow">Error</span>
        </div>
        <p class="danger">{detail}</p>
        <a class="button secondary" href="/">返回首页</a>
    </div>
    """
    return render_page("请求失败", body)
