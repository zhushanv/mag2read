# 数据库设计文档

## 1. 设计目标

本项目的数据库主要服务于任务管理，而不是保存 OCR 的全部内容。

数据库负责保存：

- 上传任务的基本信息。
- 当前处理进度和状态。
- 每个处理阶段的执行结果。
- 页面级预览所需的元数据。
- 输入文件、过程文件和导出文件的索引。

数据库不直接保存：

- 原始 PDF。
- 页面 PNG 图片。
- OCR 完整 JSON。
- layout JSON。
- EPUB、DOCX、Markdown 等导出文件。

这些大文件继续保存在任务目录：

```text
backend/storage/tasks/{task_id}/
  input/
  pages/
  layout_raw/
  layout/
  ocr/
  clean/
  output/
```

这种设计可以让 MySQL 保持轻量，FastAPI 查询任务也更快。后续如果要从本地文件系统切换到 MinIO 或 OSS，只需要调整文件路径和文件存储模块，不需要重做数据库结构。

## 2. 总体关系

第一阶段使用 5 张业务核心表，另预留 1 张用户表：

```text
users
tasks
task_files
task_pages
task_steps
export_records
```

关系如下：

```text
users 1 --- N tasks
tasks 1 --- N task_files
tasks 1 --- N task_pages
tasks 1 --- N task_steps
tasks 1 --- N export_records
```

如果第一阶段不做登录系统，`users` 可以先不接入业务，只在 `tasks.user_id` 中预留字段。

## 3. 表设计

### 3.1 users

用户表。第一阶段可以只放默认用户，后续再扩展登录、管理员和历史任务隔离。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK, AUTO_INCREMENT | 用户 ID |
| username | VARCHAR(64) | UNIQUE, NOT NULL | 用户名 |
| password_hash | VARCHAR(255) | NULL | 密码哈希，第一阶段可为空 |
| role | VARCHAR(32) | NOT NULL, DEFAULT `user` | `user` / `admin` |
| created_at | DATETIME | NOT NULL | 创建时间 |
| updated_at | DATETIME | NOT NULL | 更新时间 |

### 3.2 tasks

任务主表。每次上传 PDF 或图片批次，就创建一条任务。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK, AUTO_INCREMENT | 数据库自增 ID |
| task_id | VARCHAR(64) | UNIQUE, NOT NULL | 对外暴露的任务 ID，也是 storage 目录名 |
| user_id | BIGINT | NULL, INDEX | 创建用户，第一阶段可为空 |
| original_name | VARCHAR(255) | NOT NULL | 原始文件名或批次名 |
| input_type | VARCHAR(32) | NOT NULL | `pdf` / `image` / `image_directory` |
| status | VARCHAR(32) | NOT NULL | `pending` / `processing` / `success` / `failed` / `cancelled` |
| current_stage | VARCHAR(64) | NULL | 当前阶段，例如 `ocr` |
| progress | TINYINT | NOT NULL, DEFAULT 0 | 整体进度，范围 0-100 |
| storage_dir | VARCHAR(500) | NOT NULL | 任务目录路径 |
| page_count | INT | NULL | 页面数量 |
| output_format | VARCHAR(128) | NULL | 用户选择的导出格式，例如 `epub,markdown` |
| error_message | TEXT | NULL | 失败原因 |
| created_at | DATETIME | NOT NULL | 创建时间 |
| started_at | DATETIME | NULL | 开始处理时间 |
| finished_at | DATETIME | NULL | 完成时间 |
| updated_at | DATETIME | NOT NULL | 更新时间 |

任务状态建议：

```text
pending      等待队列处理
processing   正在处理
success      全部完成
failed       处理失败
cancelled    用户取消或系统终止
```

`tasks` 主要服务这几个接口：

- 任务列表。
- 任务详情。
- 总进度条。
- 失败原因展示。

### 3.3 task_files

文件索引表。它不保存文件内容，只保存文件路径和用途。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK, AUTO_INCREMENT | 文件记录 ID |
| task_id | VARCHAR(64) | NOT NULL, INDEX | 所属任务 |
| file_role | VARCHAR(64) | NOT NULL | 文件用途 |
| file_name | VARCHAR(255) | NOT NULL | 文件名 |
| file_path | VARCHAR(500) | NOT NULL | 文件路径 |
| mime_type | VARCHAR(128) | NULL | MIME 类型 |
| file_size | BIGINT | NULL | 文件大小 |
| page_no | INT | NULL | 所属页码，非页面文件为空 |
| created_at | DATETIME | NOT NULL | 创建时间 |

常见 `file_role`：

```text
input_pdf
input_image
page_image
layout_raw_json
layout_json
ocr_json
clean_json
cleaning_report
markdown
epub
docx
html
txt
```

前端需要预览页面、下载文件时，可以先查这张表。

### 3.4 task_pages

页面表。每一页对应一条记录，用于页面列表、质量检查和调试预览。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK, AUTO_INCREMENT | 页面记录 ID |
| task_id | VARCHAR(64) | NOT NULL, INDEX | 所属任务 |
| page_no | INT | NOT NULL | 页码，从 1 开始 |
| image_path | VARCHAR(500) | NOT NULL | 页面 PNG 路径 |
| width | INT | NULL | 页面宽度 |
| height | INT | NULL | 页面高度 |
| quality_status | VARCHAR(32) | NULL | `ok` / `warning` / `review` |
| page_type | VARCHAR(64) | NULL | `book_text` / `paper` / `magazine_complex` 等 |
| layout_type | VARCHAR(64) | NULL | `single_column` / `double_column` / `mixed_complex` |
| ocr_status | VARCHAR(32) | NULL | `pending` / `success` / `failed` |
| avg_confidence | DECIMAL(5,4) | NULL | OCR 平均置信度 |
| need_review | BOOLEAN | NOT NULL, DEFAULT FALSE | 是否需要人工检查 |
| created_at | DATETIME | NOT NULL | 创建时间 |
| updated_at | DATETIME | NOT NULL | 更新时间 |

推荐唯一索引：

```text
UNIQUE(task_id, page_no)
```

这张表主要用于前端“页面预览工作台”：

- 左侧页面缩略列表。
- 标记低质量页面。
- 标记复杂版面页面。
- 展示 OCR 置信度。

### 3.5 task_steps

流程步骤表。用于记录每个处理阶段的状态、耗时和统计信息。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK, AUTO_INCREMENT | 步骤记录 ID |
| task_id | VARCHAR(64) | NOT NULL, INDEX | 所属任务 |
| stage | VARCHAR(64) | NOT NULL | 阶段名 |
| status | VARCHAR(32) | NOT NULL | `pending` / `processing` / `success` / `failed` / `skipped` |
| progress | TINYINT | NOT NULL, DEFAULT 0 | 当前阶段进度 |
| started_at | DATETIME | NULL | 开始时间 |
| finished_at | DATETIME | NULL | 结束时间 |
| duration_ms | INT | NULL | 耗时 |
| summary_json | JSON | NULL | 阶段统计信息 |
| error_message | TEXT | NULL | 失败原因 |
| created_at | DATETIME | NOT NULL | 创建时间 |
| updated_at | DATETIME | NOT NULL | 更新时间 |

推荐唯一索引：

```text
UNIQUE(task_id, stage)
```

推荐阶段名：

```text
render
layout_detect
layout_refine
ocr
text_cleaning
document_build
export
ai_reading
```

这张表是前端进度流水线的数据来源。前端不需要解析本地 JSON，只需要请求后端接口，后端读取 `task_steps` 即可返回每一步状态。

### 3.6 export_records

导出记录表。每生成一个结果文件，就写入一条记录。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK, AUTO_INCREMENT | 导出记录 ID |
| task_id | VARCHAR(64) | NOT NULL, INDEX | 所属任务 |
| format | VARCHAR(32) | NOT NULL | `markdown` / `epub` / `docx` / `html` / `txt` |
| file_path | VARCHAR(500) | NULL | 导出文件路径 |
| file_size | BIGINT | NULL | 文件大小 |
| status | VARCHAR(32) | NOT NULL | `success` / `failed` |
| error_message | TEXT | NULL | 导出失败原因 |
| created_at | DATETIME | NOT NULL | 创建时间 |

推荐索引：

```text
INDEX(task_id, format)
```

前端下载区直接读取这张表。

## 4. 任务处理时的数据写入流程

### 4.1 上传阶段

用户上传文件后：

1. 在 `tasks` 创建任务，状态为 `pending`。
2. 在 `task_files` 写入原始输入文件记录。
3. 创建任务目录：

```text
backend/storage/tasks/{task_id}/
```

### 4.2 渲染阶段

执行 PDF 或图片转页面：

1. 更新 `tasks.status = processing`。
2. 更新 `tasks.current_stage = render`。
3. 更新或创建 `task_steps(stage=render)`。
4. 每生成一页图片，写入 `task_pages`。
5. 每个页面图片写入 `task_files(file_role=page_image)`。

### 4.3 版面分析和 OCR 阶段

执行 layout 和 OCR：

1. 每个阶段更新对应的 `task_steps`。
2. 写入 layout JSON、OCR JSON 到文件目录。
3. 在 `task_files` 中记录 JSON 文件路径。
4. 更新 `task_pages.page_type`、`layout_type`、`avg_confidence`、`need_review`。

### 4.4 文本清洗和导出阶段

执行文本清洗和格式导出：

1. `clean/document.json` 写入 `task_files(file_role=clean_json)`。
2. Markdown、EPUB、DOCX 等结果写入 `output/`。
3. 每个导出结果写入 `export_records`。
4. 全部成功后更新 `tasks.status = success`、`progress = 100`。

如果任意阶段失败：

1. 当前 `task_steps.status = failed`。
2. 当前 `task_steps.error_message` 写入错误信息。
3. `tasks.status = failed`。
4. `tasks.error_message` 写入简要错误。

## 5. MySQL DDL 草案

下面是第一阶段可以直接落地的建表草案。后续接入 SQLAlchemy 和 Alembic 时，可以按这个结构转成 ORM 模型和 migration。

项目中已经提供初始化脚本：

```text
backend/database/init_mysql.sql
```

执行方式：

```bash
mysql -u root -p < backend/database/init_mysql.sql
```

执行后输入 MySQL root 密码即可。不要把数据库密码写入 SQL 文件或提交到代码仓库。

```sql
CREATE TABLE users (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  username VARCHAR(64) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NULL,
  role VARCHAR(32) NOT NULL DEFAULT 'user',
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);

CREATE TABLE tasks (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id VARCHAR(64) NOT NULL UNIQUE,
  user_id BIGINT NULL,
  original_name VARCHAR(255) NOT NULL,
  input_type VARCHAR(32) NOT NULL,
  status VARCHAR(32) NOT NULL,
  current_stage VARCHAR(64) NULL,
  progress TINYINT NOT NULL DEFAULT 0,
  storage_dir VARCHAR(500) NOT NULL,
  page_count INT NULL,
  output_format VARCHAR(128) NULL,
  error_message TEXT NULL,
  created_at DATETIME NOT NULL,
  started_at DATETIME NULL,
  finished_at DATETIME NULL,
  updated_at DATETIME NOT NULL,
  INDEX idx_tasks_user_id (user_id),
  INDEX idx_tasks_status (status),
  INDEX idx_tasks_created_at (created_at)
);

CREATE TABLE task_files (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id VARCHAR(64) NOT NULL,
  file_role VARCHAR(64) NOT NULL,
  file_name VARCHAR(255) NOT NULL,
  file_path VARCHAR(500) NOT NULL,
  mime_type VARCHAR(128) NULL,
  file_size BIGINT NULL,
  page_no INT NULL,
  created_at DATETIME NOT NULL,
  INDEX idx_task_files_task_id (task_id),
  INDEX idx_task_files_role (task_id, file_role),
  INDEX idx_task_files_page (task_id, page_no)
);

CREATE TABLE task_pages (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id VARCHAR(64) NOT NULL,
  page_no INT NOT NULL,
  image_path VARCHAR(500) NOT NULL,
  width INT NULL,
  height INT NULL,
  quality_status VARCHAR(32) NULL,
  page_type VARCHAR(64) NULL,
  layout_type VARCHAR(64) NULL,
  ocr_status VARCHAR(32) NULL,
  avg_confidence DECIMAL(5,4) NULL,
  need_review BOOLEAN NOT NULL DEFAULT FALSE,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_task_pages_task_page (task_id, page_no),
  INDEX idx_task_pages_review (task_id, need_review),
  INDEX idx_task_pages_type (task_id, page_type)
);

CREATE TABLE task_steps (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id VARCHAR(64) NOT NULL,
  stage VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  progress TINYINT NOT NULL DEFAULT 0,
  started_at DATETIME NULL,
  finished_at DATETIME NULL,
  duration_ms INT NULL,
  summary_json JSON NULL,
  error_message TEXT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_task_steps_task_stage (task_id, stage),
  INDEX idx_task_steps_status (task_id, status)
);

CREATE TABLE export_records (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id VARCHAR(64) NOT NULL,
  format VARCHAR(32) NOT NULL,
  file_path VARCHAR(500) NULL,
  file_size BIGINT NULL,
  status VARCHAR(32) NOT NULL,
  error_message TEXT NULL,
  created_at DATETIME NOT NULL,
  INDEX idx_export_records_task_format (task_id, format),
  INDEX idx_export_records_status (task_id, status)
);
```

## 6. 第一阶段暂不做的表

下面这些表可以后续再加，不建议第一阶段提前实现：

| 表 | 用途 | 暂缓原因 |
| --- | --- | --- |
| `document_texts` | 保存清洗后全文、关键词、摘要 | 第一阶段文件中的 `clean/document.json` 已够用 |
| `manual_corrections` | 保存人工修改过的 OCR 文本和版面块 | 需要先完成前端校对交互 |
| `ai_reading_records` | 保存 AI 导读请求、模型、token、结果 | AI 导读暂缓开发 |
| `api_keys` | 管理大模型 API Key | 第一阶段可用环境变量 |
| `system_logs` | 统一系统日志 | 可以先用日志文件 |

## 7. 和前端页面的对应关系

| 前端页面 | 主要读取的表 |
| --- | --- |
| 任务列表 | `tasks` |
| 任务详情 | `tasks`、`task_steps` |
| 页面预览 | `task_pages`、`task_files` |
| OCR/版面调试 | `task_pages`、`task_files`，再读取对应 JSON 文件 |
| 下载结果 | `export_records` |
| 错误排查 | `tasks.error_message`、`task_steps.error_message` |

## 8. 和后端模块的对应关系

| 后端模块 | 主要写入 |
| --- | --- |
| `render.py` | `tasks`、`task_pages`、`task_files`、`task_steps(render)` |
| `layout_detect.py` | `task_files`、`task_steps(layout_detect)` |
| `layout_refine.py` | `task_pages`、`task_files`、`task_steps(layout_refine)` |
| `ocr.py` | `task_pages`、`task_files`、`task_steps(ocr)` |
| `text_cleaning.py` | `task_files`、`task_steps(text_cleaning)` |
| `document_build.py` | `task_files`、`task_steps(document_build)` |
| `export_document.py` | `export_records`、`task_files`、`task_steps(export)` |

## 9. 实现顺序建议

第一阶段建议按下面顺序实现：

1. 先实现 SQLAlchemy ORM：`tasks`、`task_steps`。
2. 接入上传接口，上传后创建 `tasks` 记录。
3. 接入 Celery，任务启动时更新 `task_steps`。
4. 渲染页面后写入 `task_pages` 和 `task_files`.
5. OCR、清洗、导出阶段逐步补齐数据库写入。
6. 前端先基于 `tasks` 和 `task_steps` 做任务列表与进度条。
7. 再基于 `task_pages` 和 `task_files` 做页面预览。

这样做可以避免一开始就被数据库细节拖住，同时又能保证后续前端需要的数据都有地方落。
