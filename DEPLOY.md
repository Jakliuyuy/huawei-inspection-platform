# 华为巡检云平台部署说明

## 1. 准备环境

```bash
cp .env.example .env
mkdir -p data/runtime data/uploads data/reports
mkdir -p storage/backups
mkdir -p certs
```

- 修改 `.env` 中的默认管理员账号密码
- 当前默认 `docker-compose.yml` 只启动后端服务，`certs/` 目录仅为可选 Nginx 网关预留

## 2. 当前默认启动方式

```bash
docker compose up -d --build
```

默认服务监听：

```text
http://127.0.0.1:8080
```

可用性检查：

```bash
docker compose ps
curl http://127.0.0.1:8080/api/health
```

## 3. 环境变量

示例配置见 `.env.example`。

当前关键参数：

- `PORT`：服务端口，默认 `8080`
- `SESSION_HOURS`：登录会话时长，默认 `12`
- `RETENTION_DAYS`：任务和审计日志保留天数，默认 `30`
- `MAX_JOB_WORKERS`：后台任务线程数，默认 `2`
- `MAX_UPLOAD_BYTES`：上传总大小限制，默认 `209715200`
- `MAX_EXTRACTED_BYTES`：ZIP 解压总大小限制，默认 `1073741824`
- `MAX_EXTRACTED_FILES`：ZIP 解压文件数限制，默认 `5000`
- `SECURE_COOKIES`：是否仅通过 HTTPS 发送 Cookie，默认 `false`
- `DEFAULT_ADMIN_USERNAME`：默认管理员用户名
- `DEFAULT_ADMIN_PASSWORD`：默认管理员密码

## 4. 企业交付

当前仓库默认以单后端镜像交付：

- `huawei-inspection-backend`

构建镜像：

```bash
docker compose build
```

导出镜像：

```bash
bash scripts/export_images.sh
```

导入镜像：

```bash
bash scripts/load_images.sh
```

如需企业自定义模板或报告配置，可使用：

- `docker-compose.override-config.yml`
- `docker-compose.override-templates.yml`

启动方式：

```bash
docker compose -f docker-compose.yml -f docker-compose.override-config.yml up -d
docker compose -f docker-compose.yml -f docker-compose.override-templates.yml up -d
```

## 5. 数据目录

- `data/runtime/app.db`：SQLite 数据库
- `data/uploads/`：上传的原始日志和处理中间文件
- `data/reports/`：生成的 Word 报告和打包结果
- `assets/templates/`：Word 模板
- `config/report.json`：报告配置
- `storage/backups/`：备份文件

运行期数据和备份不进入镜像。

## 6. 可选 Nginx 网关

仓库中的 `nginx/` 目录保留为可选网关交付物，不包含在当前默认 `docker-compose.yml` 中。

如果需要前端静态资源托管、反向代理和 HTTPS：

- 使用 `nginx/Dockerfile` 构建前端静态资源镜像
- 使用 `nginx/conf.d/hw.conf` 作为网关配置基础
- 将证书放入 `certs/fullchain.pem` 与 `certs/privkey.pem`

当前 Nginx 配置已包含：

- `/api/*` 反向代理
- `/app/assets/*` 长缓存
- `/app/index.html` 的 `no-store`

## 7. 当前已完成的部署相关优化

- `docker-compose.yml` 已增加健康检查
- 后端镜像已改为仅复制运行必需文件，不再 `COPY . .`
- 后端镜像已改为非 root 用户运行
- 镜像内已增加 `HEALTHCHECK`
- 服务启动时会自动恢复异常中断任务，并重建报告索引

## 8. 验证命令

建议部署后执行：

```bash
python3 -m py_compile server.py backend/*.py core/*.py
docker compose config
docker build -t huawei-inspection-backend:test .
cd web && npm run lint
cd web && npm run build
curl http://127.0.0.1:8080/api/health
```

## 9. 首次登录

- 默认管理员账号密码来自 `.env`
- 首次登录后建议立即修改管理员密码，并创建正式用户
