# Huawei Inspection Platform

华为巡检云平台，用于上传巡检日志、自动生成 Word 巡检报告，并提供任务中心、系统管理、审计日志和报告管理能力。

## 功能概览

- 支持上传 ZIP 压缩包或日志目录
- 自动识别日志目录结构并生成 Word 报告
- 任务进度可视化，状态中文显示
- 支持任务详情、结果下载、报告打包下载
- 任务 ID 使用 `YYYYMMDD-序号` 规则生成
- 管理员可管理用户、重置密码、删除任务
- 管理员可按日期和用户查看服务器累计生成的 Word 报告
- 支持审计日志查看和分页
- 前端已拆分为独立 React SPA，管理页采用模块化结构

## 技术栈

- Backend: FastAPI
- Frontend: React + Vite + Ant Design
- Report Engine: python-docx
- Database: SQLite
- Reverse Proxy: Nginx
- Deployment: Docker Compose

## 项目结构

```text
.
├── server.py              # FastAPI API 服务入口与路由编排
├── backend/               # 后端持久化与报告索引模块
├── core/                  # 报告生成核心逻辑
├── assets/templates/      # Word 模板库
├── config/report.json     # 报告生成配置
├── web/                   # 独立 React 前端项目
│   └── src/
│       ├── pages/         # 页面级组件
│       ├── components/    # 复用 UI 组件
│       ├── hooks/         # 业务 hooks
│       └── lib/           # API、类型、格式化工具
├── nginx/                 # Nginx 配置
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

## 快速启动

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
- `web/` 与 `nginx/` 目录保留为独立前端和可选网关交付物
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
- Nginx 可选网关配置增加了静态资源长缓存与 `index.html` 的 `no-store`

## 管理能力

管理员可在系统管理中执行以下操作：

- 新增用户
- 重置任意用户密码
- 更新系统公告
- 删除已完成或失败任务
- 下载或删除 Word 报告
- 查看审计日志

## 开发说明

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
- 当前默认 `docker-compose.yml` 只启动后端服务；如果需要前端静态资源与 HTTPS 网关，请额外使用 `nginx/` 目录中的可选交付物

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
