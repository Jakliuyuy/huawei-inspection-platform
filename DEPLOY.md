# 华为巡检云平台部署说明

## 1. 准备

```bash
cp .env.example .env
mkdir -p certs
mkdir -p data
```

- 将 HTTPS 证书放到 `cloud/certs/fullchain.pem` 和 `cloud/certs/privkey.pem`
- 修改 `.env` 中的默认管理员账号密码

## 2. 启动

```bash
docker compose up -d --build
```

访问 `https://<你的域名或IP>/`

## 3. 数据目录

- `data/runtime/app.db`：SQLite 数据库
- `data/uploads/`：用户上传的原始日志
- `data/reports/`：生成的报告和打包结果
- `assets/templates/`：Word 模板
- `config/report.json`：报告配置

## 4. 反向代理

- `80` 端口仅做 HTTPS 跳转
- `443` 端口提供正式访问

## 5. 首次登录

- 默认管理员来自 `cloud/.env`
- 登录后到管理后台创建正式用户，并及时修改默认管理员密码
