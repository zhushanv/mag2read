# 需求说明书

## 1. 项目背景

PDF 文件在学习、办公和资料归档中使用广泛，但扫描版 PDF 往往只包含页面图像，无法直接复制文字、搜索内容或进行二次编辑。传统 PDF 转 Word 工具对扫描件支持有限，对多栏排版、杂志、论文和教材类文档的处理效果也不稳定。

本项目拟开发一个基于 Python 后端和 React 前端的全栈 PDF OCR 转换系统，重点解决扫描版 PDF 的文字识别、版面结构恢复和多格式导出问题。系统既满足个人日常使用，也可以作为课程结业项目展示完整的软件工程能力。

## 2. 项目目标

本项目的核心目标如下：

- 支持扫描版 PDF 上传与自动识别。
- 对 PDF 页面进行图片渲染和 OCR 文字识别。
- 识别页面中的标题、段落、图片、表格、页眉页脚等区域。
- 按阅读顺序重组文档内容。
- 支持导出为 DOCX、EPUB、HTML、Markdown、TXT。
- 提供 React Web 界面，支持任务进度显示和转换结果下载。
- 保存转换历史，便于用户管理文件。

## 3. 用户角色

### 普通用户

主要使用系统完成 PDF 转换，关注上传是否方便、识别是否准确、导出是否好用。

### 项目评审教师

关注系统是否具备完整功能、技术难度、工程规范、创新点和演示效果。

### 系统管理员

负责部署系统、查看任务状态、清理历史文件和维护运行环境。

## 4. 核心功能需求

### 4.1 文件上传

- 支持上传 PDF 文件。
- 限制文件类型为 `.pdf`。
- 可配置最大文件大小，例如 100 MB。
- 上传后生成唯一文件 ID。
- 保存原始文件名、文件大小、上传时间等信息。

### 4.2 PDF 类型判断

系统应自动判断 PDF 类型：

- 文本型 PDF：页面中存在可提取文字。
- 扫描型 PDF：页面主要由图片组成，文本不可直接提取。
- 混合型 PDF：部分页面有文本，部分页面为扫描图像。

判断结果用于选择后续处理流程。

### 4.3 OCR 识别

OCR 是本项目的核心功能。

系统应支持：

- 将 PDF 页面渲染为图片。
- 对页面图片进行预处理，如灰度化、去噪、二值化、倾斜校正。
- 调用 OCR 引擎识别文字。
- 获取文字内容、置信度、坐标框。
- 支持中文和英文识别。
- 对低置信度识别结果进行标记。

推荐 OCR 引擎：

- 首选 PaddleOCR，中文识别效果好，适合课程项目展示。
- 可选 Tesseract，部署简单，但中文效果通常弱于 PaddleOCR。

### 4.4 版面分析

系统应对 OCR 结果进行版面分析：

- 识别标题、正文、图片、表格、页眉、页脚、页码等区域。
- 支持多栏文本排序。
- 支持按坐标恢复阅读顺序。
- 支持过滤重复页眉页脚。
- 支持图注与图片关联。

基础版本可以使用坐标规则实现。增强版本可以引入 PaddleOCR PP-Structure、LayoutParser 或 Detectron2 版面检测模型。

### 4.5 文档结构重建

系统需要把 OCR 原始结果转换为统一的中间文档结构，便于导出不同格式。

中间结构应包含：

- 文档标题
- 页面列表
- 内容块列表
- 内容块类型
- 文本内容
- 坐标信息
- 图片路径
- 表格数据
- 识别置信度

### 4.6 多格式导出

系统应支持以下导出格式：

- DOCX：适合二次编辑，保留标题、段落、图片和表格。
- EPUB：适合电子书阅读，强调流式阅读体验。
- HTML：适合网页预览和调试版面结构。
- Markdown：适合学习笔记和知识库整理。
- TXT：适合纯文本提取。

其中 DOCX 和 EPUB 是重点展示格式。

### 4.7 任务管理

PDF OCR 转换耗时较长，应采用异步任务。

系统应支持：

- 创建转换任务。
- 查询任务状态。
- 显示转换进度。
- 记录失败原因。
- 支持任务结果下载。
- 保存转换历史。

任务状态建议：

- `pending`：等待处理
- `processing`：处理中
- `success`：转换成功
- `failed`：转换失败

### 4.8 前端页面

React 前端应包含：

- 文件上传页面
- 转换格式选择
- OCR 语言选择
- 是否启用版面分析的开关
- 任务进度页面
- 转换历史页面
- 转换结果预览页面
- 文件下载入口

## 5. 非功能需求

### 5.1 性能需求

- 普通 10 页扫描 PDF 应在可接受时间内完成识别。
- OCR 任务应在后台执行，不阻塞 Web 接口。
- 大文件处理时应显示进度。

### 5.2 可用性需求

- 前端操作流程应简洁。
- 错误信息应明确，例如文件过大、OCR 失败、导出失败。
- 转换完成后应提供直接下载按钮。

### 5.3 可维护性需求

- OCR、版面分析、格式导出应拆分为独立模块。
- 增加新导出格式时，不应大幅修改现有逻辑。
- 统一使用中间文档结构连接识别和导出流程。

### 5.4 安全需求

- 限制上传文件类型。
- 文件名应重新生成，避免路径注入。
- 输出文件应隔离存储。
- 可定期清理历史文件。

## 6. 项目边界

本项目不承诺 100% 还原所有复杂 PDF 的原始版式。PDF 本身通常不保存完整语义结构，尤其是扫描版 PDF，只能通过 OCR 和版面分析进行近似恢复。

项目重点是：

- 尽可能准确地识别文字。
- 尽可能合理地恢复阅读顺序。
- 对常见教材、论文、讲义、杂志页面提供可用的转换结果。

## 7. 技术框架选型

### 7.1 总体架构

本项目采用前后端分离架构。

前端负责文件上传、任务进度展示、页面预览、版面框叠加、OCR 文本检查和结果下载。后端负责文件管理、任务调度、PDF 页面渲染、版面分析、OCR、文本清洗、文档结构构建和格式导出。

推荐部署形态：

```text
React 前端
  ↓ HTTP/WebSocket
FastAPI 后端服务
  ↓ 创建任务/查询任务/下载结果
MySQL 数据库
  ↓ 投递长任务
Redis 队列
  ↓ 消费任务
OCR Worker
  ↓ 读写文件
backend/storage/tasks/{task_id}/
```

第一阶段可以本地单机运行，后续再扩展为 Docker Compose 部署。

### 7.2 前端技术栈

前端采用：

- React
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui
- lucide-react
- TanStack Query
- Zustand
- React Router
- react-konva

选型说明：

- React + TypeScript 适合构建复杂交互页面。
- Vite 启动快，适合课程项目快速开发。
- Tailwind CSS + shadcn/ui 可以快速做出质量较高的工具型界面。
- TanStack Query 用于管理接口请求、任务状态轮询和缓存。
- Zustand 用于保存前端局部状态，例如当前选中的页面、当前高亮的 OCR block。
- react-konva 用于页面图片上的版面框、OCR 坐标框、点击选择和图层叠加。

### 7.3 后端技术栈

后端采用：

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- MySQL
- Redis
- Celery
- PaddleOCR / PP-DocLayout
- PyMuPDF
- Pillow
- EbookLib / python-docx / Markdown 导出逻辑

选型说明：

- FastAPI 负责提供上传、任务查询、预览和下载接口。
- SQLAlchemy 负责数据库访问，Alembic 负责数据库迁移。
- MySQL 保存任务、文件、页面、步骤、导出记录等元数据。
- Redis + Celery 负责异步任务队列，避免 OCR 长任务阻塞 Web 请求。
- OCR 和版面分析放在 Worker 中执行，不直接在 FastAPI 请求线程中运行。

### 7.4 后端代码分层

后端建议按以下方式组织：

```text
backend/app/
  api/          FastAPI 路由
  core/         配置、路径、数据库、日志
  models/       SQLAlchemy ORM 模型
  schemas/      Pydantic 请求和响应结构
  modules/      PDF渲染、版面分析、OCR、清洗、导出等核心处理模块
  pipeline/     流程编排
  workers/      Celery 任务入口
```

当前已经整理出的 `backend/app/modules` 可以继续作为核心处理层，后续 FastAPI 和 Worker 都调用这一层。

## 8. 数据库设计

详细数据库设计见：[database-design.md](database-design.md)。

### 8.1 设计原则

数据库只保存元数据，不保存大文件本体。

PDF、页面图片、OCR JSON、清洗结果、Markdown、EPUB 等文件保存在任务目录中：

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

MySQL 保存这些信息：

- 任务是谁创建的。
- 任务当前处理到哪一步。
- 每一步是否成功。
- 输入文件和输出文件在哪里。
- 每页的基本信息和处理状态。
- 失败原因、耗时、统计信息。

这样设计的好处是：

- 数据库不会因为图片和 JSON 过大而膨胀。
- 文件结构和当前处理流水线保持一致。
- 后续可以把本地文件存储替换为 MinIO、OSS 或其他对象存储。

### 8.2 核心表

第一阶段建议使用 5 张业务核心表，另预留 1 张用户表：

```text
users
tasks
task_files
task_pages
task_steps
export_records
```

如果第一版不做登录，可以先不启用 `users`，但表结构中保留 `user_id` 字段，方便后续扩展。

### 8.3 users 用户表

用于保存用户信息。课程项目第一阶段可以只放一个默认用户。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 用户 ID |
| username | VARCHAR(64) | 用户名 |
| password_hash | VARCHAR(255) | 密码哈希，第一阶段可为空 |
| role | VARCHAR(32) | `user` / `admin` |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### 8.4 tasks 任务主表

这是最重要的表。每上传一个 PDF 或图片批次，就创建一条任务。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 数据库自增 ID |
| task_id | VARCHAR(64) UNIQUE | 对外暴露的任务 ID，对应 storage 目录名 |
| user_id | BIGINT NULL | 创建用户，第一阶段可为空 |
| original_name | VARCHAR(255) | 原始文件名或批次名 |
| input_type | VARCHAR(32) | `pdf` / `image` / `image_directory` |
| status | VARCHAR(32) | `pending` / `processing` / `success` / `failed` / `cancelled` |
| current_stage | VARCHAR(64) | 当前阶段，例如 `ocr`、`text_cleaning` |
| progress | TINYINT | 0-100 的整体进度 |
| storage_dir | VARCHAR(500) | 任务目录路径 |
| page_count | INT | 页面数量 |
| output_format | VARCHAR(128) | 用户选择的导出格式，例如 `epub,markdown` |
| error_message | TEXT NULL | 失败原因 |
| created_at | DATETIME | 创建时间 |
| started_at | DATETIME NULL | 开始处理时间 |
| finished_at | DATETIME NULL | 完成时间 |
| updated_at | DATETIME | 更新时间 |

任务状态建议：

```text
pending      等待队列处理
processing   正在处理
success      全部完成
failed       处理失败
cancelled    用户取消或系统终止
```

### 8.5 task_files 文件表

保存输入文件、过程文件和输出文件的索引。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 文件记录 ID |
| task_id | VARCHAR(64) | 所属任务 |
| file_role | VARCHAR(64) | `input_pdf` / `page_image` / `ocr_json` / `clean_json` / `markdown` / `epub` |
| file_name | VARCHAR(255) | 文件名 |
| file_path | VARCHAR(500) | 文件路径 |
| mime_type | VARCHAR(128) | 文件类型 |
| file_size | BIGINT | 文件大小 |
| page_no | INT NULL | 所属页码，非页面文件可为空 |
| created_at | DATETIME | 创建时间 |

这个表不是为了替代目录结构，而是为了让前端和 API 快速知道“有哪些文件可以预览或下载”。

### 8.6 task_pages 页面表

每个页面一条记录，用于页面级预览和调试。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 页面记录 ID |
| task_id | VARCHAR(64) | 所属任务 |
| page_no | INT | 页码，从 1 开始 |
| image_path | VARCHAR(500) | 页面 PNG 路径 |
| width | INT | 页面宽度 |
| height | INT | 页面高度 |
| quality_status | VARCHAR(32) | `ok` / `warning` / `review` |
| page_type | VARCHAR(64) | `book_text` / `paper` / `magazine_complex` 等 |
| layout_type | VARCHAR(64) | `single_column` / `double_column` / `mixed_complex` |
| ocr_status | VARCHAR(32) | `pending` / `success` / `failed` |
| avg_confidence | DECIMAL(5,4) NULL | OCR 平均置信度 |
| need_review | BOOLEAN | 是否需要人工检查 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

页面表主要服务前端预览页，例如左侧页面列表可以直接显示哪些页低质量、哪些页需要检查。

### 8.7 task_steps 流程步骤表

用于记录每个阶段的开始时间、结束时间、状态和错误信息。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 步骤记录 ID |
| task_id | VARCHAR(64) | 所属任务 |
| stage | VARCHAR(64) | `render` / `layout_detect` / `layout_refine` / `ocr` / `text_cleaning` / `document_build` / `export` / `ai_reading` |
| status | VARCHAR(32) | `pending` / `processing` / `success` / `failed` / `skipped` |
| progress | TINYINT | 当前步骤进度 |
| started_at | DATETIME NULL | 开始时间 |
| finished_at | DATETIME NULL | 结束时间 |
| duration_ms | INT NULL | 耗时 |
| summary_json | JSON NULL | 阶段统计信息 |
| error_message | TEXT NULL | 失败原因 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

这张表解决“用户看到的进度条从哪里来”的问题。前端展示流水线时，不需要解析本地 JSON，只需要读 `task_steps`。

### 8.8 export_records 导出记录表

每生成一个导出文件，就写一条记录。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 导出记录 ID |
| task_id | VARCHAR(64) | 所属任务 |
| format | VARCHAR(32) | `markdown` / `epub` / `docx` / `html` / `txt` |
| file_path | VARCHAR(500) | 导出文件路径 |
| file_size | BIGINT | 文件大小 |
| status | VARCHAR(32) | `success` / `failed` |
| error_message | TEXT NULL | 导出失败原因 |
| created_at | DATETIME | 创建时间 |

前端下载区直接读取这张表。

### 8.9 表之间的关系

```text
users 1 --- N tasks
tasks 1 --- N task_files
tasks 1 --- N task_pages
tasks 1 --- N task_steps
tasks 1 --- N export_records
```

第一阶段可以不做复杂外键约束，只建立索引：

```text
tasks.task_id UNIQUE
task_files.task_id INDEX
task_pages.task_id + page_no UNIQUE
task_steps.task_id + stage UNIQUE
export_records.task_id + format INDEX
```

### 8.10 为什么不把 OCR 文本全文放进 MySQL

OCR 结果通常包含大量坐标、置信度、行框、多边形和调试信息，直接放数据库会让表变得臃肿，也不方便人工检查。

推荐做法：

- 完整 OCR 结果保存在 `ocr/page_*.json`。
- 清洗后的完整文档保存在 `clean/document.json`。
- MySQL 只保存路径、状态、统计值和必要摘要。

如果后续要做全文搜索，可以再单独增加一张 `document_texts` 表，保存清洗后的纯文本和关键词；第一阶段不需要提前做。
