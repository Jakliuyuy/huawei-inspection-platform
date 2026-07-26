# 华为巡检云平台部署说明

## 1. 准备环境

```bash
cp .env.example .env
mkdir -p data/runtime data/uploads data/reports
mkdir -p storage/backups
mkdir -p certs
```

- 修改 `.env` 中的默认管理员账号密码
- 当前默认 `docker-compose.yml` 只启动后端服务

## 2. 当前默认启动方式

```bash
docker compose up -d --build
```

镜像是多阶段构建，**前端在镜像里一起构建**，宿主机不需要装 Node。
容器只监听 `127.0.0.1:8080`，对外由系统 Nginx 反代。

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
- `MAX_EMAIL_FILES` / `MAX_EMAIL_RECIPIENTS`：单次发信的文件数与收件人数上限，各默认 `20`
- `SECURE_COOKIES`：不设置时按 `LOCAL_MODE` 自动取值（线上 `true` / 本地 `false`），一般无需配置
- `LOCAL_MODE`：免登录单用户模式，只监听 `127.0.0.1`。**线上务必保持 `false`**
- `FRONTEND_DIR`：前端产物目录，默认 `web/dist`；目录不存在则跳过静态托管
- `DEFAULT_ADMIN_USERNAME`：默认管理员用户名
- `DEFAULT_ADMIN_PASSWORD`：默认管理员密码。**留空会用代码兜底值，务必设成 ≥12 位随机字符**
- `SMTP_USERNAME` / `SMTP_PASSWORD`：留空则发信端点直接返回 400（测试环境正是靠这个保证不会误发）

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

## 6. 系统网关

仓库内不再维护 Nginx 配置文件。

如果需要前端静态资源托管、反向代理和 HTTPS，请直接维护系统级配置：

- `/etc/nginx/conf.d`
- `/etc/nginx/nginx.conf`
- 证书文件路径由你当前主机的 Nginx 配置自行决定

### 6.1 后端隐含依赖的 Nginx 约定（必读）

以下几条不在仓库里，但后端代码直接依赖它们。改动任何一条都会让线上出问题，
而**本地开发全部测不出来**，因为本地走的是另一条代码分支。

| 约定 | 依赖它的代码 | 配错的后果 |
|---|---|---|
| `/api/*` 反代到 `127.0.0.1:8080` | 全部接口 | 整站不可用 |
| `/_protected-reports/*` 必须是 `internal`，alias 到 `data/reports/` | `backend/downloads.py` | **漏了 `internal` 时该路径就是免鉴权的公开下载入口**，而 job_id 形如 `20260727-001` 极易枚举 |
| `/app/` 指向前端产物目录，且带 `try_files ... /app/index.html` | 前端路由 | 刷新 `/app/tasks/xxx` 深链 404 |
| `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;` | `backend/security.py:client_ip` | 登录限流退化为全站共用一个桶（任何人错 5 次全站锁 5 分钟），审计 IP 全部相同 |
| `client_max_body_size` ≥ `MAX_UPLOAD_BYTES`（默认 200M） | 上传接口 | 大包上传被 Nginx 直接拒绝 |
| `proxy_read_timeout` 足够长 | 上传 + 9 个系统生成 | 长任务被中断 |

`X-Accel-Redirect` 分支的触发条件是**请求里有没有 `X-Forwarded-For` 头**
（`backend/downloads.py`）。也就是说下载在本地和线上走的是完全不同的两段代码，
本地永远走 `FileResponse`。改动 `data/reports/` 的目录布局前务必意识到这一点。

上线后建议核对一次：

```bash
nginx -T | grep -A5 _protected-reports   # 确认有 internal
```

其余：静态资源缓存策略、HTTPS 证书与跳转规则按需配置。

## 7. 部署形态要点

- 镜像多阶段构建：node 阶段产出 `web/dist`，运行阶段只带运行必需文件，非 root 用户
- 镜像自带一份前端产物。Nginx 配了 `/app/` 就走 Nginx，没配则后端接管；
  两者共存，镜像那份同时是前端的第二个回滚源
- 容器与镜像内均有 `HEALTHCHECK`
- 启动时自动：建表/增量加列 → 重建报告索引 → 恢复异常中断任务 → 清理过期数据与暂存
- **数据库只追加可空列与新表**，新旧镜像互相兼容 —— 回滚镜像时数据库不必一起回退
- `data/` 始终外置，不进镜像
- Nginx 配置由系统 `/etc/nginx/conf.d` 统一管理，仓库不再维护

## 8. 验证命令

建议部署后执行：

```bash
python3 -m pytest                      # 报告黄金基线 + API 冒烟 + 本地模式
docker compose config
docker build -t huawei-inspection-backend:test .
cd web && npm run lint && npm run lint:css && npm run build
curl http://127.0.0.1:8080/api/health
```

其中 `pytest` 里的黄金基线会用真实日志跑一遍报告生成并逐字比对文本指纹，
是判断"改动有没有影响报告内容"的唯一可靠手段。基线数据在 `tests/golden/`，
**只有在人工确认差异符合预期后**才用 `python tests/make_golden.py` 刷新。

## 9. 首次登录

- 默认管理员账号密码来自 `.env`
- 首次登录后建议立即修改管理员密码，并创建正式用户
