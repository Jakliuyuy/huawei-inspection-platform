# 华为巡检云平台部署说明

## 1. 准备

```bash
cp .env.example .env
mkdir -p certs
mkdir -p data/runtime data/uploads data/reports
mkdir -p storage/backups
```

- 将 HTTPS 证书放到 `cloud/certs/fullchain.pem` 和 `cloud/certs/privkey.pem`
- 修改 `.env` 中的默认管理员账号密码

## 2. 标准启动

```bash
docker compose up -d --build
```

访问 `https://<你的域名或IP>/app/login`

## 3. 企业交付

导出镜像：

```bash
bash scripts/export_images.sh
```

导入镜像：

```bash
bash scripts/load_images.sh
```

如需企业自定义模板或报告配置，创建：

- `overrides/templates/`
- `overrides/report.json`

然后执行：

```bash
docker compose -f docker-compose.yml -f docker-compose.override-config.yml up -d
docker compose -f docker-compose.yml -f docker-compose.override-templates.yml up -d
```

## 4. 数据目录

- `data/runtime/app.db`：SQLite 数据库
- `data/uploads/`：用户上传的原始日志
- `data/reports/`：生成的报告和打包结果
- `assets/templates/`：Word 模板
- `config/report.json`：报告配置
- `storage/backups/`：备份文件

运行期数据、证书、备份不进入镜像。

## 5. 反向代理

- `80` 端口仅做 HTTPS 跳转
- `443` 端口提供正式访问

## 6. 首次登录

- 默认管理员来自 `cloud/.env`
- 登录后到管理后台创建正式用户，并及时修改默认管理员密码
