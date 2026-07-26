# legacy/desktop — 已废弃的本地脚本

`app.py`（CustomTkinter 桌面 GUI）与 `run.py`（命令行）曾是本地生成巡检报告的入口，
通过 `sys.path.insert` 直接 import 仓库里的 `core.generate_reports`。

网页版补齐它们的独有能力后，本地改为直接跑后端（`LOCAL_MODE=true`）+ 浏览器上传，
这两个脚本随之废弃。**保留在此仅作行为规格参考**，不参与构建、不在部署路径上。

保留的原因：它们此前从不在任何版本控制之下，而其中三段逻辑是网页版新能力的唯一书面规格。

---

## 一、必须被网页版覆盖的三个能力

### 1. 按系统选择性生成

桌面版做法（`app.py:524-528`）：把 `config/report.json` 过滤后写成临时的
`report_filtered.json`，再作为 `ReportPaths.config_path` 传入。

> **⚠️ 网页版故意没有照抄这个做法。**
>
> `generate_reports` 会把整份 config 作为 `all_configs` 传给 `process_system`，
> 最终喂给 `LogObject.__init__`（`core/report_service.py:122-123`）：
>
> ```python
> is_sys_prefix = any(key.upper() in prefix
>                     for key in list(all_config.keys()) + ["NETMGMT","NM","SMS","GPRS"])
> self.file_subject = (parts[1] if len(parts) >= 2 and is_sys_prefix else parts[0]).lower()
> ```
>
> 也就是说 **`all_config` 参与解析日志文件名**。把它换成过滤后的子集，
> 可能改变 `file_subject`，进而改变设备匹配结果——这不是我们想要的语义。
>
> 网页版改为给 `generate_reports` 传 `only_systems`，**只过滤遍历集合，
> `all_configs` 始终传全量 config**。代价为零，且从构造上绕开了这个问题。
>
> 回归测试锁定了这一点：`only_systems={"TOC"}` 产出的 TOC 报告，
> 文本指纹必须与全量跑出的 TOC 报告完全一致。

另注：`app.py:525` 与 `run.py:193` 写的是**同一个固定路径** `report_filtered.json`，
网页版存在任务并发，照抄必然互相覆盖——这是不照抄的第二个理由。

### 2. 上传后、生成前的逐系统日志完整度预览

规格在 `app.py:92-108` `preview_system_stats()`：

- `expected = len(sys_info["hosts"])`，**为 0 时回落为 `actual`**（NM1/NM2/NM3 没有 hosts 清单）
- 日志目录名兼容：`log_root/<KEY>` 找不到时回落 `log_root/<KEY.replace("NM","NetMgmt")>`（`app.py:100`）
- 统计 `*.log` 数量作为 `actual`

> 注意：桌面版统计 `actual` 时**没有跳过 summary 文件**，而 `process_system`
> 生成时会跳过（`core/report_service.py`）。网页版统一用同一个过滤谓词，
> 否则预览的"实到"会虚高。

### 3. 自定义报告日期

`app.py:508` / `run.py:162` 都用 `datetime.strptime(value, "%Y-%m-%d")` 校验。
桌面版**不持久化日期**（每次启动用今天），这是修过的行为——早期版本会用上次保存的
旧日期覆盖今天，导致次日打开时静默生成日期错误的报告。

---

## 二、`run.py` 的命令行能力对照

| 参数 | 作用 | 网页版对应 |
|---|---|---|
| `log_dir`（位置参数） | 直接指定本地目录，不走上传 | 无（网页版必须上传，受 `MAX_UPLOAD_BYTES` 限制） |
| `-s/--system`（可重复） | 只处理指定系统，含未知 key 校验（`run.py:187-191`） | `POST /api/jobs` 的 `systems[]` |
| `-d/--date` | 报告日期 | `POST /api/jobs` 的 `report_date` |
| `-o/--output` | 输出目录 | 无（固定 `data/reports/<job_id>`，改用"打开该目录"替代） |
| `-w/--workers` | 并行进程数，`1` 为串行调试 | 环境变量 `MAX_REPORT_WORKERS` |
| `--list` | 列出全部系统 | `GET /api/systems` |

---

## 三、删除条件

只有当以下全部成立时，才可以 `git rm -r legacy/desktop/`（历史里仍可查）：

1. 网页版三个新能力已实现并通过回归测试
2. 本地 `LOCAL_MODE` 跑通，浏览器上传可用
3. `run.py` 的批量/脚本化场景确认已被覆盖或明确放弃
