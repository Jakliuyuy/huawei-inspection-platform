# Overrides

该目录用于企业部署时按需覆盖默认资源。

- `templates/`：可选，自定义 Word 模板目录
- `report.json`：可选，自定义报告配置文件，可从 `report.json.example` 复制

默认部署无需挂载本目录。
只有需要企业定制模板或配置时，才在启动命令中追加：

```bash
docker compose -f docker-compose.yml -f docker-compose.override-config.yml up -d
docker compose -f docker-compose.yml -f docker-compose.override-templates.yml up -d
```
