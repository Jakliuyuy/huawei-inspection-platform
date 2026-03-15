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
├── server.py              # FastAPI API 服务
├── core/                  # 报告生成核心逻辑
├── web/                   # 独立 React 前端项目
│   └── src/
│       ├── pages/         # 页面级组件
│       ├── components/    # 复用 UI 组件
│       ├── hooks/         # 业务 hooks
│       └── lib/           # API、类型、格式化工具
├── nginx/                 # Nginx 配置
├── Word_模板库/           # Word 模板库
├── data/                  # 运行数据、上传文件、生成报告
├── docker-compose.yml     # Docker 编排
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

将 HTTPS 证书放到：

- `certs/fullchain.pem`
- `certs/privkey.pem`

并修改 `.env` 中的默认管理员账号和密码。

### 2. 启动服务

```bash
docker compose up -d --build
```

访问：

```text
https://<你的域名或IP>/app/login
```

## 默认运行目录

- `data/runtime/app.db`：SQLite 数据库
- `data/uploads/`：上传的原始日志及处理中间文件
- `data/reports/`：生成的 Word 报告和打包结果

## 当前部署结构

- `app` 容器运行 FastAPI
- `nginx` 容器构建并托管 React 静态资源，同时反向代理 `/api/*`
- 80 端口强制跳转到 443
- 443 端口提供正式访问
- `/app/*` 为前端路由入口
- `/api/*` 为后端接口入口
- `/`、`/dashboard`、`/upload`、`/admin` 等旧路径会自动跳转到新 SPA 页面

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

- `server.py` 提供 `/api/*` 接口
- `web/` 提供 React SPA，统一挂载在 `/app/*`
- 根路径和旧页面路径会自动跳转到对应 SPA 页面
- 管理后台已拆为用户、任务、Word 报告、审计四个独立模块

## 注意事项

- 上传文件总大小受 `MAX_UPLOAD_BYTES` 控制，默认 200 MB

## 首次登录

- 默认管理员账号密码来自 `.env`
- 首次登录后建议立即修改管理员密码，并创建正式用户
