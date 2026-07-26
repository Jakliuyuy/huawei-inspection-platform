# Huawei Inspection Platform

华为巡检云平台，用于上传巡检日志、自动生成 Word 巡检报告，并提供任务中心、系统管理、审计日志和报告管理能力。

## 功能概览

- 支持上传 ZIP 压缩包或日志目录
- **上传后先解析预览**：逐系统显示实到/应到设备数，可只勾选需要生成的系统
- **可自定义报告日期**：默认从日志目录名推断，补跑历史日志不会写成当天
- 自动识别日志目录结构并生成 Word 报告
- 任务进度可视化，状态中文显示
- 支持任务详情、结果下载、报告打包下载
- 任务 ID 使用 `YYYYMMDD-序号` 规则生成
- 管理员可管理用户、重置密码、删除任务
- 管理员可按日期和用户查看服务器累计生成的 Word 报告
- 支持审计日志查看和分页
- 按系统白名单分发邮件，收件人由服务端校验（客户端只能删减，不能添加配置外地址）
- 前端 React SPA，支持浅色/深色主题
- **本地免登录模式**：一条命令启动，无需 Nginx 或 Node

## 技术栈

- Backend: FastAPI
- Frontend: React + Vite + Ant Design
- Report Engine: python-docx
- Database: SQLite
- Reverse Proxy: External Nginx or other gateway
- Deployment: Docker Compose

## 项目结构

```text
.
├── server.py              # 应用入口：装配路由、lifespan、静态托管（约 70 行）
├── backend/               # 后端实现
│   ├── config.py          # 配置与全局常量
│   ├── db.py              # 连接、建表、增量加列
│   ├── security.py        # 密码/令牌哈希、真实客户端 IP
│   ├── auth.py            # 会话、登录限流、鉴权守卫（LOCAL_MODE 唯一分支点）
│   ├── queries.py         # 任务/公告/报告索引查询
│   ├── serializers.py     # 行 -> 响应
│   ├── paths.py           # 报告路径解析（统一的越界防线）
│   ├── uploads.py         # 落盘、安全解压、目录布局识别
│   ├── upload_sessions.py # 上传暂存会话与解析预览
│   ├── storage.py         # 任务产物磁盘管理
│   ├── downloads.py       # 下载响应（Nginx X-Accel 契约的唯一承载点）
│   ├── jobs.py            # 任务线程池与生成编排
│   ├── mail.py            # 邮件主题与收件人白名单
│   ├── static_files.py    # 前端托管（含 SPA history fallback）
│   └── routes/            # APIRouter：auth/meta/uploads/jobs/email/admin
├── core/                  # 报告生成核心（纯库，零 Web 依赖）
│   ├── report_service.py  # 生成编排与设备匹配
│   ├── log_layout.py      # 目录解析与完整度统计（预览与生成共用）
│   └── docx_engine.py     # Word 填充引擎
├── tests/                 # 黄金基线 + API 冒烟 + 本地模式
├── assets/templates/      # Word 模板库
├── config/report.json     # 报告生成配置
├── web/                   # 独立 React 前端项目
│   └── src/
│       ├── pages/         # 页面级组件
│       ├── components/    # 复用 UI 组件
│       ├── hooks/         # 业务 hooks
│       ├── theme/         # 设计系统 token 与主题切换
│       └── lib/           # API、类型、文件处理
├── data/                  # 运行数据、上传文件、生成报告
├── overrides/             # 企业可选覆盖模板与配置
├── scripts/               # 镜像导入导出脚本
├── release/               # 企业交付导出目录
├── samples/               # 示例日志目录
├── storage/backups/       # 手工备份文件
├── docker-compose.yml     # Docker 编排
├── docker-compose.override-config.yml     # 可选覆盖报告配置
├── docker-compose.override-templates.yml  # 可选覆盖 Word 模板
├── Dockerfile             # 应用镜像
└── DEPLOY.md              # 简要部署说明
```

## 本地运行（免登录，一条命令）

把仓库拷到本地后：

```bash
pip install -r requirements.txt
cd web && npm ci && npm run build && cd ..

# Windows PowerShell:  $env:LOCAL_MODE="true"; python server.py
LOCAL_MODE=true python server.py
```

然后打开 <http://localhost:8080/app/>，直接进主界面，无需登录。

- 本地模式只监听 `127.0.0.1`（免登录 + 公网 = 灾难，所以不给选）
- 生成的报告在 `data/reports/<job_id>/`，可直接用资源管理器打开
- 改前端时用 `cd web && npm run dev`（已配 `/api` 代理与 Secure Cookie 剥离）

线上部署不设 `LOCAL_MODE`，鉴权照常。

## 快速启动（服务器部署）

### 1. 准备环境

```bash
cp .env.example .env
mkdir -p certs
mkdir -p data
```

并修改 `.env` 中的默认管理员账号和密码。

### 2. 启动服务

```bash
docker compose up -d --build
```

默认接口监听：

```text
http://127.0.0.1:8080
```

## 在另一台机器部署

如果你要在另一台新机器直接从 Git 仓库部署，按下面步骤即可。

### 1. 克隆仓库

```bash
git clone https://github.com/Jakliuyuy/huawei-inspection-platform.git
cd huawei-inspection-platform
```

### 2. 准备运行目录和环境变量

```bash
cp .env.example .env
mkdir -p data/runtime data/uploads data/reports
mkdir -p storage/backups
mkdir -p certs
```

至少建议修改 `.env` 中这些参数：

- `DEFAULT_ADMIN_USERNAME`
- `DEFAULT_ADMIN_PASSWORD`
- `SECURE_COOKIES`
- `SESSION_HOURS`
- `RETENTION_DAYS`

### 3. 启动后端

```bash
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:8080/api/health
```

默认后端仅监听：

```text
127.0.0.1:8080
```

### 4. 如果需要网页访问

当前仓库默认 `docker-compose.yml` 只启动后端服务。

如果你需要完整网页访问能力，还需要单独处理前端和网关：

1. 构建前端

```bash
cd web
npm install
npm run build
```

2. 配置系统级 Nginx 或其他网关

建议至少包含：

- `/api/` 反向代理到 `127.0.0.1:8080`
- `/app/` 指向前端打包后的静态文件目录
- `/_protected-reports/` 映射到 `data/reports/`，用于报告下载

### 5. 如果需要迁移旧机器数据

把老机器这些目录或文件同步到新机器即可：

- `data/runtime/app.db`
- `data/uploads/`
- `data/reports/`

如果你还有自定义模板或报告配置，再同步：

- `assets/templates/`
- `config/report.json`

### 6. 端口说明

当前 `docker-compose.yml` 使用：

```yaml
ports:
  - "127.0.0.1:8080:8080"
```

这意味着默认只能本机访问。

如果你需要局域网或公网直接访问，有两种常见方式：

- 改成 `0.0.0.0:8080:8080`
- 保持 `127.0.0.1:8080`，再由 Nginx 反向代理对外提供服务

## 企业标准版交付

默认当前仓库交付以单后端镜像为主：

- `huawei-inspection-backend`

构建镜像：

```bash
docker compose build
```

导出交付包：

```bash
bash scripts/export_images.sh
```

交付目录会生成到 `release/`，包含：

- `backend-image.tar`
- `docker-compose.yml`
- `docker-compose.override-config.yml`
- `docker-compose.override-templates.yml`
- `.env.example`

企业侧导入镜像：

```bash
bash scripts/load_images.sh
```

企业如果要覆盖模板或报告配置，使用：

```bash
docker compose -f docker-compose.yml -f docker-compose.override-config.yml up -d
docker compose -f docker-compose.yml -f docker-compose.override-templates.yml up -d
```

## 默认运行目录

- `data/runtime/app.db`：SQLite 数据库
- `data/uploads/`：上传的原始日志及处理中间文件
- `data/reports/`：生成的 Word 报告和打包结果
- `assets/templates/`：Word 模板文件
- `config/report.json`：报告系统映射配置
- `samples/`：示例日志，非运行必需
- `storage/backups/`：备份产物，非运行必需

## 当前部署结构

- `app` 镜像运行 FastAPI
- 当前 `docker-compose.yml` 仅编排后端容器，默认监听 `127.0.0.1:8080`
- 仓库不再维护 Nginx 配置文件，网关统一由系统 `/etc/nginx/conf.d` 管理
- `/api/*` 为后端接口入口
- `/`、`/dashboard`、`/upload`、`/admin` 等旧路径会自动跳转到新 SPA 页面
- 默认模板与默认 `config/report.json` 已内置进后端镜像
- `data/`、`storage/` 始终外置，不进入镜像

## 最近已完成优化

### 后端稳定性

- 任务 ID 创建改为数据库锁保护下的原子分配，避免并发创建任务时出现重复 `YYYYMMDD-序号`
- SQLite 连接默认启用 `WAL`、`busy_timeout`、`foreign_keys`
- 为会话、任务、审计日志、报告索引补充了常用索引
- 服务启动时会自动恢复未完成任务，将异常中断的 `queued` / `running` 任务标记为失败
- `/api/health` 不再只返回固定 JSON，而会实际探测数据库连接

### 上传与文件安全

- 上传总大小继续受 `MAX_UPLOAD_BYTES` 限制
- ZIP 解压新增 `MAX_EXTRACTED_BYTES` 和 `MAX_EXTRACTED_FILES` 两层限制，防止异常压缩包拖垮磁盘与 CPU
- 上传保存失败时会自动回滚任务记录并清理任务目录，避免脏数据残留

### 任务与管理接口

- `/api/jobs` 和 `/api/admin/jobs` 已改为分页接口，返回：
  - `items`
  - `page`
  - `page_size`
  - `total`
  - `total_pages`
  - `stats`
- 仪表盘与管理后台任务表格已接入分页，不再全量拉取全部任务
- 仪表盘统计卡片改为使用后端汇总统计，而不是只基于当前页计算

### 报告管理性能

- 新增 `report_files` 表，用于持久化 Word 报告索引
- 管理后台“Word 报告”查询不再每次扫描 `jobs.generated_files` 和磁盘文件，而是直接走数据库聚合
- 任务完成、任务删除、单个报告删除时都会同步维护 `report_files`
- 服务启动时会自动重建报告索引，兼容旧数据

### 前端体验与构建

- `usePolling` 改为基于 `useEffectEvent` 的稳定轮询，避免因为 render 导致定时器频繁重建
- 管理页数据 hooks 清理了 effect 依赖问题，`npm run lint` 可通过
- Vite 手工分包继续细化，Ant Design 被拆成 `antd-basic`、`antd-feedback`、`antd-layout`、`antd-form`、`antd-data` 等更细的 chunk
- 当前构建产物中，原本单个超大 `antd-core` 主包已被明显拆散，缓存复用更合理

### 后端结构重构

- 将数据库与列表分页相关逻辑拆到 `backend/persistence.py`
- 将报告索引与报告聚合查询相关逻辑拆到 `backend/reports.py`
- `server.py` 目前主要保留路由、认证编排、任务编排和文件处理入口

### 镜像与交付

- `Dockerfile` 改为只复制运行必需文件，不再 `COPY . .`
- 后端镜像改为非 root 用户运行
- 镜像内增加 `HEALTHCHECK`
- `docker-compose.yml` 增加容器健康检查
- `.env.example` 已补充新的 ZIP 解压限制参数，并修正了 `SECURE_COOKIES` 默认值拼写错误
- 仓库内不再维护 Nginx 交付物，网关配置统一转移到系统 `/etc/nginx/conf.d`

## 创建任务的接口流程

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

其他新增：`GET /api/systems`（系统清单，对应旧 CLI 的 `--list`）、
`GET/DELETE /api/uploads/{id}`。

## 管理能力

管理员可在系统管理中执行以下操作：

- 新增用户
- 重置任意用户密码
- 更新系统公告
- 删除已完成或失败任务
- 下载或删除 Word 报告
- 查看审计日志

## 开发说明

### 样式约定

antd 组件的外观一律走 `web/src/theme/components.ts` 的 token，**不要写 `.ant-*` 选择器**。
自定义容器用 CSS Modules，里面只允许 `var(--app-*)`，不允许出现 hex 色值——
这样暗色模式自动跟随，不必写两套。stylelint 会强制这两条（`npm run lint:css`）。

需要改 antd 外观时依次尝试：组件级 token → 组件自身的 `classNames`/`styles` →
`ConfigProvider` 的组件级默认 props。三者都不行，说明该用自定义 DOM 而不是 antd 组件。


当前项目已经拆分为独立前后端：

- `server.py` 提供 `/api/*` 接口和应用入口
- `backend/persistence.py` 提供任务分页、审计分页、用户列表、过期清理、异常恢复
- `backend/reports.py` 提供报告索引重建、报告聚合查询、报告文件索引同步
- `web/` 提供 React SPA，统一挂载在 `/app/*`
- 根路径和旧页面路径会自动跳转到对应 SPA 页面
- 管理后台已拆为用户、任务、Word 报告、审计四个独立模块

## 当前关键参数

- `SESSION_HOURS`：登录会话时长，默认 `12`
- `RETENTION_DAYS`：任务与审计日志保留天数，默认 `30`
- `MAX_JOB_WORKERS`：后台任务线程数，默认 `2`
- `MAX_UPLOAD_BYTES`：上传总大小限制，默认 `209715200`
- `MAX_EXTRACTED_BYTES`：ZIP 解压总大小限制，默认 `1073741824`
- `MAX_EXTRACTED_FILES`：ZIP 解压文件数限制，默认 `5000`
- `SECURE_COOKIES`：Cookie 是否仅 HTTPS 发送，默认 `false`

## 注意事项

- 上传文件总大小受 `MAX_UPLOAD_BYTES` 控制，默认 200 MB
- ZIP 解压后的总大小受 `MAX_EXTRACTED_BYTES` 控制，默认 1 GB
- ZIP 解压后的文件数受 `MAX_EXTRACTED_FILES` 控制，默认 5000
- 当前默认 `docker-compose.yml` 只启动后端服务；如需反向代理与 HTTPS，请直接维护系统 `/etc/nginx/conf.d`

## 验证记录

本轮优化后，已实际验证以下命令可通过：

```bash
python3 -m py_compile server.py backend/*.py core/*.py
docker compose config
docker build -t huawei-inspection-backend:test .
cd web && npm run lint
cd web && npm run build
```

## 首次登录

- 默认管理员账号密码来自 `.env`
- 首次登录后建议立即修改管理员密码，并创建正式用户
