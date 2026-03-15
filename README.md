# Huawei Inspection Platform

华为巡检云平台，用于上传巡检日志、自动生成 Word 巡检报告，并提供任务中心、系统管理、审计日志和报告管理能力。

## 功能概览

- 支持上传 ZIP 压缩包或日志目录
- 自动识别日志目录结构并生成 Word 报告
- 任务进度可视化，状态中文显示
- 支持任务详情、结果下载、报告打包下载
- 管理员可管理用户、重置密码、删除任务
- 管理员可按日期和用户查看服务器累计生成的 Word 报告
- 支持审计日志查看和分页

## 技术栈

- Backend: FastAPI
- Report Engine: python-docx
- Database: SQLite
- Reverse Proxy: Nginx
- Deployment: Docker Compose

## 项目结构

```text
.
├── server.py              # 主服务入口
├── core/                  # 报告生成核心逻辑
├── frontend/              # 当前服务端渲染前端模块
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
https://<你的域名或IP>/
```

## 默认运行目录

- `data/runtime/app.db`：SQLite 数据库
- `data/uploads/`：上传的原始日志及处理中间文件
- `data/reports/`：生成的 Word 报告和打包结果

## 当前部署结构

- `app` 容器运行 FastAPI
- `nginx` 容器提供 HTTPS 和反向代理
- 80 端口强制跳转到 443
- 443 端口提供正式访问

## 管理能力

管理员可在系统管理中执行以下操作：

- 新增用户
- 重置任意用户密码
- 更新系统公告
- 删除已完成或失败任务
- 下载或删除 Word 报告
- 查看审计日志

## 开发说明

当前项目仍处于后端主导阶段，页面渲染逻辑已从 `server.py` 抽离到 `frontend/views.py`，后续计划继续升级为独立前端项目。

## 注意事项

- 当前仓库已经包含运行数据和样例日志，仓库体积较大
- 当前仓库也包含 `.env` 和本地虚拟环境 `.venv`，如果要公开仓库，建议后续清理并重写 `.gitignore`
- 上传文件总大小受 `MAX_UPLOAD_BYTES` 控制，默认 200 MB

## 首次登录

- 默认管理员账号密码来自 `.env`
- 首次登录后建议立即修改管理员密码，并创建正式用户
