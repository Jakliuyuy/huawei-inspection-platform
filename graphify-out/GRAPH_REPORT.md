# Graph Report - C:\Users\admin\desktop\新建文件夹 (2)\huawei-inspection-platform  (2026-08-01)

## Corpus Check
- 77 files · ~4,921,487 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 515 nodes · 1030 edges · 45 communities detected
- Extraction: 59% EXTRACTED · 41% INFERRED · 0% AMBIGUOUS · INFERRED: 426 edges (avg confidence: 0.79)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]

## God Nodes (most connected - your core abstractions)
1. `get()` - 67 edges
2. `db_connect()` - 53 edges
3. `now_local()` - 34 edges
4. `record_audit()` - 30 edges
5. `require_admin()` - 25 edges
6. `require_user()` - 24 edges
7. `get_version()` - 17 edges
8. `api_create_job()` - 16 edges
9. `process_system()` - 15 edges
10. `api_login()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `db_connect()` --calls--> `list_admin_users()`  [INFERRED]
  C:\Users\admin\desktop\新建文件夹 (2)\huawei-inspection-platform\backend\db.py → C:\Users\admin\desktop\新建文件夹 (2)\huawei-inspection-platform\backend\persistence.py
- `db_connect()` --calls--> `list_audits_page()`  [INFERRED]
  C:\Users\admin\desktop\新建文件夹 (2)\huawei-inspection-platform\backend\db.py → C:\Users\admin\desktop\新建文件夹 (2)\huawei-inspection-platform\backend\persistence.py
- `任务执行：线程池、进度回写与报告生成编排。` --uses--> `ReportPaths`  [INFERRED]
  C:\Users\admin\desktop\新建文件夹 (2)\huawei-inspection-platform\backend\jobs.py → C:\Users\admin\desktop\新建文件夹 (2)\huawei-inspection-platform\core\report_service.py
- `delete_job_storage()` --calls--> `api_admin_delete_job()`  [INFERRED]
  C:\Users\admin\desktop\新建文件夹 (2)\huawei-inspection-platform\backend\storage.py → C:\Users\admin\desktop\新建文件夹 (2)\huawei-inspection-platform\backend\routes\admin.py
- `get()` --calls--> `test_no_login_required()`  [INFERRED]
  C:\Users\admin\desktop\新建文件夹 (2)\huawei-inspection-platform\backend\upload_sessions.py → C:\Users\admin\desktop\新建文件夹 (2)\huawei-inspection-platform\tests\test_local_mode.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.09
Nodes (56): api_admin_audits(), api_admin_create_user(), api_admin_delete_job(), api_admin_delete_report(), api_admin_download_report(), api_admin_jobs(), api_admin_reset_password(), api_report_dates() (+48 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (50): docx_fingerprint(), fingerprints_of(), 共享 fixture 与工具。  黄金基线的核心约束：**不能对 .docx 做二进制哈希**。docx 是 zip，内部 docProps/core.x, 按序提取 docx 的全部可见文本并哈希。, 跑一次报告生成。      max_workers=1 强制串行：进程池下 audit 行序按完成顺序 extend，     多进程时行序不确定，无法用, run_generation(), _collect_family_outputs(), _find_alias_match() (+42 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (44): job_report_names(), 报告文件路径解析。  两个解析器共用同一套防线：取 basename 归一化 → resolve → 校验仍在允许的 根目录内 → 限定 .docx 后缀, 把 file_name 当作 base 下的单个文件名解析，越界返回 None。      先取 basename 抹掉任何目录成分，再 resolve 后, resolve_job_report_path(), resolve_within(), app_module(), created_job(), fresh_upload() (+36 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (36): require_user(), build_download_response(), 文件下载响应。  ⚠️ 这是对 Nginx 的隐性契约的唯一承载点。X-Accel-Redirect 分支把路径 相对 config.report_dir, api_job_email_suggestions(), api_send_email(), _job_recipients(), 报告邮件发送。  两道安全约束在这里汇合，改动时务必保留：   1. 附件路径必须来自 generated_files 白名单（resolve_job_r, _build_message() (+28 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (36): _extract_labeled_value(), _extract_name(), _extract_prompt_name(), _find_command_columns(), _guess_driver(), inspect_docx_security(), merge_incremental_template(), parse_template() (+28 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (35): api_admin_users(), list_admin_users(), api_login(), api_logout(), api_me(), clear_login_failures(), clear_session(), clear_session_response() (+27 more)

### Community 6 - "Community 6"
Cohesion: 0.07
Nodes (30): _add_missing_columns(), ensure_dirs(), initialize_database(), api_create_job(), _create_versioned_job(), enqueue_job(), process_job(), 任务执行：线程池、进度回写与报告生成编排。 (+22 more)

### Community 7 - "Community 7"
Cohesion: 0.09
Nodes (34): detect_log_root(), iter_system_logs(), preview_system_stats(), 日志目录布局识别与完整度统计。  预览与生成**必须**共用这里的目录解析和日志筛选，否则预览报出的 "GPRS 12/15" 与生成时实际读到的文件不是, 一个系统可能对应的目录名。      配置里键是 NM1/NM2/NM3，而现场目录常写成 NetMgmt1 等。, 该系统目录下参与生成的日志文件。      summary 文件不是设备日志，生成时会跳过，统计时也必须跳过——否则     预览的"实到"会比实际参与匹, 逐系统统计实到/应到设备数。      expected 取配置里的 hosts 数量；NM1-3 没有 hosts 清单，此时回落为     实到数（完, 在上传解压后的目录里找出真正的日志根。      先看 base 自身与其直接子目录里是否含系统目录；都没有时回退到形似     日期的目录，取**最新* (+26 more)

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (17): ApiError, isUnauthorized(), request(), UploadTransportError, uploadWithProgress(), loadJobs(), buildUploadForm(), dedupeFiles() (+9 more)

### Community 9 - "Community 9"
Cohesion: 0.23
Nodes (15): get(), _index_files(), _infer_version(), 日志批次落盘、执行清单解析和严格完整度校验。, _read_text(), _row(), save_files(), _sha() (+7 more)

### Community 10 - "Community 10"
Cohesion: 0.2
Nodes (7): 本地模式：免登录、单用户、鉴权在唯一分支点上放行。  与 test_api_smoke 分开是因为 server 在导入时读环境变量，两种模式 必须各自导, localhost 走 http，Secure Cookie 会被丢弃，本地模式必须默认关闭。, 必须是真实数据库行 —— jobs.user_id 有外键约束。, test_local_user_row_exists(), test_no_login_required(), test_protected_endpoints_open_without_cookie(), test_secure_cookie_defaults_off_locally()

### Community 11 - "Community 11"
Cohesion: 0.29
Nodes (6): mount_frontend(), 前端静态文件托管。  线上仍由 Nginx 直发 /app/，容器里不带 dist 时这里自动跳过挂载； 本地把 dist 放进来，一条 python s, 带 history fallback 的静态文件。      StaticFiles(html=True) 只会去找 404.html，找不到就抛 404, 挂载前端。必须在所有 /api 路由注册之后调用。, SPAStaticFiles, StaticFiles

### Community 12 - "Community 12"
Cohesion: 0.33
Nodes (0):

### Community 13 - "Community 13"
Cohesion: 0.33
Nodes (2): ThemeProvider(), useThemeMode()

### Community 14 - "Community 14"
Cohesion: 0.5
Nodes (2): buildEntries(), load()

### Community 15 - "Community 15"
Cohesion: 0.5
Nodes (2): canDeleteJob(), isActiveStatus()

### Community 16 - "Community 16"
Cohesion: 0.67
Nodes (3): AppConfig, build_config(), 应用配置与全局常量。  从 server.py 原样搬来，唯一的实质改动是 APP_ROOT 的定位方式： 本模块位于 backend/ 下，所以要 pa

### Community 17 - "Community 17"
Cohesion: 0.5
Nodes (1): 分页参数归一与响应组装。  原先在 api_jobs / api_admin_jobs / api_admin_audits 三处逐字重复。

### Community 18 - "Community 18"
Cohesion: 0.67
Nodes (2): guard(), shell()

### Community 19 - "Community 19"
Cohesion: 0.5
Nodes (0):

### Community 20 - "Community 20"
Cohesion: 0.67
Nodes (0):

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (0):

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (0):

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (0):

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (0):

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (0):

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (0):

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (0):

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (0):

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (0):

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (0):

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (0):

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (0):

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (0):

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (0):

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (0):

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (0):

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (0):

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (0):

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (0):

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (0):

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (0):

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): 返回命令表头行及命令、结果列，兼容不同模板的列顺序。

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): 把增量文档中的设备表格追加到旧模板，保留原表格 OOXML 与样式。

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): 把增量文档中的设备表格追加到旧模板，保留原表格 OOXML 与样式。

## Knowledge Gaps
- **55 isolated node(s):** `华为巡检云平台 —— 应用入口。  真正的实现都在 backend/ 下：   config / db / security / auth / audit`, `用户查询、会话生命周期、登录限流与鉴权守卫。`, `本地模式的固定用户。启动时已 upsert，这里只查。      必须是真实存在的行：jobs.user_id 有外键约束且 PRAGMA foreign_`, `应用配置与全局常量。  从 server.py 原样搬来，唯一的实质改动是 APP_ROOT 的定位方式： 本模块位于 backend/ 下，所以要 pa`, `文件下载响应。  ⚠️ 这是对 Nginx 的隐性契约的唯一承载点。X-Accel-Redirect 分支把路径 相对 config.report_dir` (+50 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 21`** (2 nodes): `vite.config.ts`, `configure()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (2 nodes): `go()`, `AppShell.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (2 nodes): `CreateUserModal.tsx`, `CreateUserModal()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (2 nodes): `useAdminPageData.ts`, `useAdminPageData()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (2 nodes): `usePolling.ts`, `usePolling()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (2 nodes): `LoginPage.tsx`, `handleFinish()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (2 nodes): `components.ts`, `buildComponents()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (2 nodes): `ThemeBridge.tsx`, `ThemeBridge()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (2 nodes): `ThemeContext.ts`, `useTheme()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `eslint.config.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `stylelint.config.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `main.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `AuditManagementSection.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `JobManagementSection.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `ReportManagementSection.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `UserManagementSection.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `types.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `palette.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `返回命令表头行及命令、结果列，兼容不同模板的列顺序。`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `把增量文档中的设备表格追加到旧模板，保留原表格 OOXML 与样式。`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `把增量文档中的设备表格追加到旧模板，保留原表格 OOXML 与样式。`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get()` connect `Community 2` to `Community 0`, `Community 1`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 10`?**
  _High betweenness centrality (0.408) - this node is a cross-community bridge._
- **Why does `db_connect()` connect `Community 0` to `Community 2`, `Community 3`, `Community 5`, `Community 6`, `Community 7`, `Community 9`?**
  _High betweenness centrality (0.144) - this node is a cross-community bridge._
- **Why does `process_system()` connect `Community 1` to `Community 2`, `Community 4`, `Community 7`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Are the 64 inferred relationships involving `get()` (e.g. with `require_user()` and `should_rate_limit()`) actually correct?**
  _`get()` has 64 INFERRED edges - model-reasoned connections that need verification._
- **Are the 51 inferred relationships involving `db_connect()` (e.g. with `record_audit()` and `get_user_by_username()`) actually correct?**
  _`db_connect()` has 51 INFERRED edges - model-reasoned connections that need verification._
- **Are the 33 inferred relationships involving `now_local()` (e.g. with `record_audit()` and `get_user_by_session()`) actually correct?**
  _`now_local()` has 33 INFERRED edges - model-reasoned connections that need verification._
- **Are the 29 inferred relationships involving `record_audit()` (e.g. with `client_ip()` and `db_connect()`) actually correct?**
  _`record_audit()` has 29 INFERRED edges - model-reasoned connections that need verification._
