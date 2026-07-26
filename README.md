# Huawei Inspection Platform

华为巡检云平台。上传巡检日志 → 按系统确认范围 → 自动生成 Word 巡检报告 → 按白名单分发邮件。
另含任务中心、系统管理、报告归档与审计日志。

## 功能概览

- 上传 ZIP 压缩包或整个日志目录（保留层级）
- **上传后先解析预览**：逐系统显示实到 / 应到设备数，只勾选需要生成的系统
- **可自定义报告日期**：默认从日志目录名推断，补跑历史日志不会被写成当天
- 自动识别日志目录结构，并行生成 Word 报告
- 任务进度可视化，结果可单份下载或整包下载
- 按系统白名单分发邮件，收件人由服务端校验（客户端只能删减，不能添加配置外地址）
- 管理端：用户管理、任务管理、按日期/用户浏览报告归档、审计日志
- 前端 React SPA，支持浅色 / 深色主题
- **本地免登录模式**：一条命令启动，不需要 Nginx，也不需要单独装 Node

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | FastAPI + SQLite（WAL） |
| 前端 | React 19 + Vite + Ant Design 6 |
| 报告引擎 | python-docx |
| 部署 | Docker Compose（镜像内含前端产物），生产由外部 Nginx 反代 |

---

## 一、本地运行（免登录，一条命令）

适合把项目拷到自己机器上，用浏览器完成上传与生成。

```bash
pip install -r requirements.txt
cd web && npm ci && npm run build && cd ..
```

启动：

**Windows —— 双击 `start-local.bat`**（会自动打开浏览器；停止用 `stop-local.bat`，
或直接关掉那个黑窗口 / 按 Ctrl+C）。

命令行方式：

```bash
# Linux / macOS
LOCAL_MODE=true python server.py

# Windows PowerShell
$env:LOCAL_MODE="true"; python server.py
```

打开 <http://localhost:8080/app/> —— 直接进主界面，无需登录。

要点：

- 本地模式**只监听 `127.0.0.1`**。免登录 + 公网 = 灾难，所以这一条不开放配置。
- 生成的报告在 `data/reports/<job_id>/`，可以直接用资源管理器打开，不必从浏览器下载。
- 数据库、上传、报告都在 `data/` 下，删掉即可重置。
- 不配 `SMTP_*` 时发信接口直接返回 400，本地不可能误发邮件。

改前端时用开发服务器（热更新）：

```bash
cd web && npm run dev     # 5173 端口，已配 /api 代理
```

---

## 二、服务器部署

### 1. 准备

```bash
git clone https://github.com/Jakliuyuy/huawei-inspection-platform.git
cd huawei-inspection-platform
cp .env.example .env
```

**必须改 `.env` 里这两项**：

- `DEFAULT_ADMIN_PASSWORD` —— 留空会用代码兜底值，务必设成 ≥12 位随机字符
- `SMTP_USERNAME` / `SMTP_PASSWORD` —— 不配则发信功能不可用

`LOCAL_MODE` 保持 `false`（默认）。`SECURE_COOKIES` 不用管，会自动按 `LOCAL_MODE` 取值。

### 2. 启动

```bash
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:8080/api/health
```

镜像是多阶段构建，**前端在镜像里一起构建**，不需要在宿主机装 Node。
容器只监听 `127.0.0.1:8080`，对外由 Nginx 反代。

### 3. Nginx

仓库不维护 Nginx 配置，由系统 `/etc/nginx/conf.d` 管理。
**后端隐含依赖的几条约定见 [DEPLOY.md](DEPLOY.md#61-后端隐含依赖的-nginx-约定必读)** ——
其中 `/_protected-reports/` 少了 `internal` 会变成免鉴权的公开下载入口，务必核对：

```bash
nginx -T | grep -A5 _protected-reports
```

前端有两条可选路径：

- **Nginx 直发**（现状）：`/app/` 指向 `web/dist`，需配 `try_files ... /app/index.html`
- **后端托管**：镜像里已带一份 `web/dist`，Nginx 不配 `/app/` 时后端会接管

两者共存，互不冲突。镜像自带的那份也是前端的第二个回滚源。

### 4. 迁移旧机器数据

同步这些即可：

```text
data/runtime/app.db     数据库
data/uploads/           上传与中间文件
data/reports/           已生成报告
assets/templates/       自定义 Word 模板（如有改动）
config/report.json      设备清单与收件人（如有改动）
```

数据库只会**追加可空列和新表**，新旧镜像互相兼容 —— 回滚镜像时数据库不必一起回退。

### 5. 首次登录

用 `.env` 里的 `DEFAULT_ADMIN_USERNAME` / `DEFAULT_ADMIN_PASSWORD` 登录，
随后立即改密并创建正式用户。

---

## 三、项目结构

```text
.
├── server.py              # 应用入口：装配路由、lifespan、静态托管（约 70 行）
├── backend/               # 后端实现
│   ├── config.py          # 配置与全局常量
│   ├── db.py              # 连接、建表、增量加列
│   ├── security.py        # 密码/令牌哈希、真实客户端 IP
│   ├── auth.py            # 会话、登录限流、鉴权守卫（LOCAL_MODE 唯一分支点）
│   ├── audit.py           # 操作审计
│   ├── queries.py         # 任务/公告/报告索引查询
│   ├── serializers.py     # 数据库行 -> 响应
│   ├── pagination.py      # 分页参数归一与响应组装
│   ├── payloads.py        # 请求体解析（畸形请求体 -> 400 而非 500）
│   ├── paths.py           # 报告路径解析（统一的越界防线）
│   ├── uploads.py         # 落盘、安全解压、目录布局识别
│   ├── upload_sessions.py # 上传暂存会话与解析预览
│   ├── storage.py         # 任务产物磁盘管理
│   ├── downloads.py       # 下载响应（Nginx X-Accel 契约的唯一承载点）
│   ├── jobs.py            # 任务线程池与生成编排
│   ├── mail.py            # 邮件主题与收件人白名单
│   ├── email_service.py   # SMTP 传输
│   ├── persistence.py     # 任务/审计分页、过期清理、异常恢复
│   ├── reports.py         # 报告索引表
│   ├── static_files.py    # 前端托管（含 SPA history fallback）
│   └── routes/            # APIRouter：auth / meta / uploads / jobs / email / admin / legacy
├── core/                  # 报告生成核心（纯库，零 Web 依赖）
│   ├── report_service.py  # 生成编排与设备匹配
│   ├── log_layout.py      # 目录解析与完整度统计（预览与生成共用）
│   └── docx_engine.py     # Word 填充引擎
├── tests/                 # 黄金基线 + API 冒烟 + 本地模式
│   └── golden/            # 报告文本指纹与匹配审计基线
├── web/src/
│   ├── pages/             # 页面
│   ├── components/        # 组件（common/ 为共用件）
│   ├── hooks/             # 业务 hooks
│   ├── theme/             # 设计系统 token 与主题切换
│   └── lib/               # API、类型、文件处理
├── assets/templates/      # Word 模板库
├── config/report.json     # 设备清单 + 收件人白名单（单一真相）
├── start-local.bat        # Windows 本地启动（双击即用）
├── stop-local.bat         # Windows 本地停止
├── data/                  # 运行数据，始终外置，不进镜像
└── DEPLOY.md              # 部署细节与 Nginx 约定
```

`core/` 不依赖 FastAPI，可以独立调用。

---

## 四、创建任务的接口流程

上传与建任务是**两步**，这样才能在生成前把逐系统完整度摆给用户看：

```
POST   /api/uploads              multipart files[]
       -> { upload_id, log_root_label, detected, log_file_count,
            suggested_report_date,
            systems: [{ key, display_name, expected, actual, missing,
                        has_logs, output_name_template }] }

POST   /api/jobs                 { upload_id, systems[], report_date }
       -> { ok, job_id }
```

- `systems` 传空数组表示全部系统
- `report_date` 省略时用 `suggested_report_date`（从日志目录名推断，推断不出则取昨天）
- 暂存会话 2 小时过期，过期后 `POST /jobs` 返回 410，前端可用内存里的文件一键重传
- `output_name_template` 里的 `{date}` 由前端替换。**不要在前端复刻命名规则** ——
  真相在 `core/report_service.process_system`，规则一变前端预览就会骗人

其他：`GET /api/systems`（系统清单）、`GET/DELETE /api/uploads/{id}`。
`/`、`/dashboard`、`/upload`、`/admin` 等旧路径仍会 302 到对应 SPA 页面。

---

## 五、开发说明

### 测试

```bash
pip install -r requirements-dev.txt
python -m pytest
```

三组：

- **报告黄金基线** —— 用真实日志跑一遍生成，逐份比对 docx 的文本指纹与匹配审计。
  这是判断"改动有没有影响报告内容"的唯一可靠手段。
  （不能对 docx 做二进制哈希：它是 zip，内部带修改时间，每次都不同。）
- **API 冒烟** —— 端点存在性、鉴权边界、响应字段集合、路径穿越用例。
- **本地模式** —— 免登录放行、单用户播种、Cookie 策略。

基线数据在 `tests/golden/`。**只有人工确认差异符合预期后**，才用
`python tests/make_golden.py` 刷新 —— 基线的全部价值就在于它不跟着代码一起变。

测试永不发邮件：不设 `SMTP_*` 时发信端点直接返回 400。

### 样式约定

antd 组件的外观一律走 `web/src/theme/components.ts` 的 token，**不要写 `.ant-*` 选择器**。
自定义容器用 CSS Modules，里面只允许 `var(--app-*)`，不允许出现 hex 色值 ——
这样暗色模式自动跟随，不必写两套。stylelint 强制这两条。

需要改 antd 外观时依次尝试：组件级 token → 组件自身的 `classNames` / `styles` →
`ConfigProvider` 的组件级默认 props。三者都不行，说明该用自定义 DOM 而不是 antd 组件。

### 提交前

```bash
python -m pytest
cd web && npm run lint && npm run lint:css && npm run build
```

---

## 六、配置参数

| 变量 | 默认 | 说明 |
|---|---|---|
| `LOCAL_MODE` | `false` | 免登录、单用户、只监听 127.0.0.1。**线上务必保持 false** |
| `FRONTEND_DIR` | `web/dist` | 前端产物目录；不存在则跳过静态托管 |
| `SECURE_COOKIES` | 随 `LOCAL_MODE` | 不设置时自动取值（本地 false / 线上 true），一般无需配置 |
| `SESSION_HOURS` | `12` | 登录会话时长 |
| `RETENTION_DAYS` | `30` | 任务与审计日志保留天数 |
| `MAX_JOB_WORKERS` | `2` | 后台任务线程数 |
| `MAX_UPLOAD_BYTES` | 200 MB | 单次上传总大小 |
| `MAX_EXTRACTED_BYTES` | 1 GB | ZIP 解压总大小 |
| `MAX_EXTRACTED_FILES` | `5000` | ZIP 解压文件数 |
| `MAX_EMAIL_FILES` | `20` | 单次发信的文件数上限 |
| `MAX_EMAIL_RECIPIENTS` | `20` | 单个文件的收件人数上限 |
| `SMTP_HOST` / `SMTP_PORT` | `smtp.139.com` / `465` | SMTP_SSL |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | 空 | 留空则发信端点返回 400 |

`config/report.json` 是设备清单与收件人白名单的**单一真相**。新增一个系统 =
改这个文件 + 放对应 Word 模板，代码不用动。

---

## 七、管理能力

- 新增用户、重置任意用户密码（密码 ≥8 位）
- 更新系统公告
- 删除已完成或失败的任务（处理中不可删）
- 按日期 → 用户 → 文件三级浏览报告归档，可下载或删除
- 查看审计日志（含操作人、动作、IP、详情）

---

## 八、注意事项

- 上传大小受 `MAX_UPLOAD_BYTES` 限制；如果走 Nginx，`client_max_body_size` 要不小于它
- 报告下载在本地和线上走**不同代码分支**（依据请求是否带 `X-Forwarded-For`），
  改动 `data/reports/` 布局前请先读 DEPLOY.md 的 Nginx 约定一节
- `docker-compose.yml` 只编排后端；HTTPS 与反代由系统 Nginx 负责
