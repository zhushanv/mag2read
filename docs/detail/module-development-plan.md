# Mag2Read 分模块开发计划

## 1. 文档目标

本文档根据 `requirements.md` 和 `功能亮点文档.md` 整理 Mag2Read 项目的分模块开发计划。

开发原则：

- 按模块拆分，不把所有逻辑堆进一个大流程。
- 每个模块有明确输入、输出和验收标准。
- 优先完成可演示的核心闭环，再逐步补充亮点功能。
- 后端核心处理模块、FastAPI 接口、数据库、前端页面分别推进，但通过统一任务模型衔接。

项目主线：

```text
上传文件
  ↓
创建任务
  ↓
页面渲染
  ↓
图像质量检查
  ↓
版面分析
  ↓
OCR
  ↓
文本清洗与文档结构构建
  ↓
Markdown / EPUB 导出
  ↓
前端预览与下载
  ↓
AI 导读与增强功能
```

## 2. 总体模块划分

### 2.1 前端模块

```text
UI/
  src/
    pages/
    components/
    features/
    api/
    stores/
    routes/
```

建议拆分：

| 模块 | 职责 | 优先级 |
| --- | --- | --- |
| 上传与任务创建 | 文件选择、拖拽上传、格式选择、提交任务 | P0 |
| 任务列表 | 展示历史任务、状态、创建时间、失败原因 | P0 |
| 任务进度 | 展示 render、layout、ocr、clean、export 等阶段 | P0 |
| 页面预览 | 显示页面图片、页码、质量状态 | P1 |
| 版面框可视化 | 使用 react-konva 叠加 layout block 和 OCR block | P1 |
| 清洗结果预览 | 左侧页面，右侧 Markdown / 正文结构 | P1 |
| 下载区 | 下载 EPUB、Markdown、DOCX、HTML、TXT | P0 |
| 质量评分面板 | 展示 OCR 置信度、异常页、噪音过滤率 | P1 |
| AI 阅读卡片 | 展示摘要、关键词、结构脉络、思考问题 | P2 |
| 人工校正 | 编辑文本、恢复误删区块、重新导出 | P2 |

### 2.2 后端 API 模块

```text
backend/app/api/
  upload.py
  tasks.py
  pages.py
  files.py
  exports.py
  health.py
```

建议拆分：

| 模块 | 职责 | 优先级 |
| --- | --- | --- |
| 上传 API | 接收 PDF/图片，创建任务，保存文件 | P0 |
| 任务 API | 查询任务列表、任务详情、任务状态 | P0 |
| 页面 API | 查询页面列表、页面图片、页面质量信息 | P1 |
| 文件 API | 返回 layout/OCR/clean JSON 或调试文件 | P1 |
| 导出 API | 查询导出记录、下载导出文件 | P0 |
| WebSocket/SSE | 推送任务进度 | P1 |
| 健康检查 API | 检查服务、数据库、Redis、Worker 状态 | P1 |

### 2.3 后端核心处理模块

当前已经整理到：

```text
backend/app/modules/
  render.py
  layout_detect.py
  layout_refine.py
  ocr.py
  text_cleaning.py
  document_build.py
  export_document.py
```

建议继续保持单模块可调用：

| 模块 | 输入 | 输出 | 优先级 |
| --- | --- | --- | --- |
| `render.py` | PDF/图片路径 | `pages/page_*.png`、`metadata.json` | P0 |
| `layout_detect.py` | 页面图片 | `layout_raw/page_*.json`、debug overlay | P0 |
| `layout_refine.py` | layout raw JSON | `layout/page_*.json` | P0 |
| `ocr.py` | layout JSON + 页面图片 | `ocr/page_*.json` | P0 |
| `text_cleaning.py` | OCR JSON | `clean/document.json`、清洗报告 | P0 |
| `document_build.py` | clean document | `book.md`、章节结构 | P0 |
| `export_document.py` | clean document | EPUB、DOCX、HTML、TXT | P0/P1 |

### 2.4 Pipeline 和 Worker 模块

```text
backend/app/pipeline/
  task_runner.py

backend/app/workers/
  celery_app.py
  tasks.py
```

职责：

- 串联已有核心处理模块。
- 处理任务状态流转。
- 更新 `tasks`、`task_steps`、`task_pages`、`task_files`、`export_records`。
- 捕获错误并写入数据库。
- 支持单阶段重跑，例如只重跑 OCR 或只重跑导出。

### 2.5 数据库模块

```text
backend/app/models/
backend/app/schemas/
backend/app/core/database.py
backend/database/init_mysql.sql
```

职责：

- SQLAlchemy ORM 模型。
- Pydantic 请求/响应模型。
- 数据库连接和 session 管理。
- Alembic 迁移。
- 初始化 SQL 对照。

核心表：

```text
users
tasks
task_files
task_pages
task_steps
export_records
```

## 3. 开发阶段规划

## 阶段 0：项目基础设施整理

目标：让前后端、数据库、队列具备可开发基础。

任务：

- 确认前端技术栈：React + TypeScript + Vite。
- 确认后端技术栈：FastAPI + SQLAlchemy + MySQL。
- 确认异步任务：Redis + Celery。
- 保留现有 `backend/app/modules` 模块化结构。
- 创建数据库初始化脚本和数据库设计文档。
- 补充 `.env` 配置方案。

验收标准：

- 可以启动 FastAPI。
- 可以连接 MySQL。
- 可以连接 Redis。
- 可以执行数据库初始化 SQL。
- 后端核心模块仍可单独运行。

状态：部分已完成。

## 阶段 1：任务与数据库基础模块

目标：先把任务管理打稳，避免后续前端和 Worker 没有统一状态来源。

后端开发内容：

- 实现数据库连接模块。
- 实现 ORM 模型：
  - `User`
  - `Task`
  - `TaskFile`
  - `TaskPage`
  - `TaskStep`
  - `ExportRecord`
- 实现 Pydantic schemas。
- 实现任务状态枚举和阶段枚举。
- 实现任务仓储/服务层：
  - 创建任务
  - 更新任务状态
  - 创建或更新步骤状态
  - 写入文件记录
  - 写入页面记录
  - 写入导出记录

前端开发内容：

- 暂时不做复杂 UI。
- 可先做任务列表 mock 页面，等 API 稳定后对接。

验收标准：

- 上传前可以手动创建一条任务记录。
- 可以查询任务列表。
- 可以查询单个任务详情。
- 可以查询任务步骤列表。

## 阶段 2：文件上传与任务创建模块

目标：完成用户从前端上传文件到后端创建任务的闭环。

后端开发内容：

- `POST /api/tasks/upload`
- 校验文件类型：PDF、JPG、PNG。
- 校验文件大小。
- 生成 `task_id`。
- 创建任务目录。
- 保存原始文件到 `input/`。
- 写入 `tasks`。
- 写入 `task_files(file_role=input_pdf/input_image)`。
- 投递 Celery 任务。

前端开发内容：

- 上传页面。
- 拖拽上传。
- 文件类型和大小提示。
- 上传后跳转任务详情页。

验收标准：

- 上传文件后数据库出现任务记录。
- `backend/storage/tasks/{task_id}/input/` 下有原始文件。
- 前端能拿到 `task_id` 并进入任务详情页。

## 阶段 3：异步任务与处理流水线模块

目标：把已有后端处理模块接入 Celery 和数据库状态。

后端开发内容：

- Celery 初始化。
- Worker 任务入口。
- 串联处理阶段：
  - `render`
  - `layout_detect`
  - `layout_refine`
  - `ocr`
  - `text_cleaning`
  - `document_build`
  - `export`
- 每个阶段开始时更新 `task_steps.status = processing`。
- 每个阶段结束时写入 `summary_json`。
- 阶段失败时写入错误信息。
- 总任务状态同步更新。

验收标准：

- 上传任务后 Worker 能自动处理。
- 数据库能看到每个阶段的状态变化。
- 处理失败时前端能看到失败原因。
- 处理成功后 `tasks.status = success`。

## 阶段 4：前端任务进度与下载闭环

目标：完成用户可见的最小可用产品。

后端开发内容：

- `GET /api/tasks`
- `GET /api/tasks/{task_id}`
- `GET /api/tasks/{task_id}/steps`
- `GET /api/tasks/{task_id}/exports`
- `GET /api/exports/{export_id}/download`

前端开发内容：

- 任务列表页。
- 任务详情页。
- 阶段进度条。
- 成功/失败状态展示。
- 下载区。

验收标准：

- 用户可以上传文件。
- 用户可以看到处理进度。
- 用户可以下载 Markdown / EPUB。
- 核心闭环可演示。

## 阶段 5：页面预览与可解释清洗模块

目标：实现功能亮点中的“可解释清洗预览”。

后端开发内容：

- `GET /api/tasks/{task_id}/pages`
- `GET /api/tasks/{task_id}/pages/{page_no}`
- `GET /api/tasks/{task_id}/pages/{page_no}/image`
- `GET /api/tasks/{task_id}/pages/{page_no}/layout`
- `GET /api/tasks/{task_id}/pages/{page_no}/ocr`
- `GET /api/tasks/{task_id}/clean-document`

前端开发内容：

- 页面缩略列表。
- 页面图片预览。
- 使用 react-konva 叠加 layout block。
- 区分标题、正文、图注、页眉页脚、页码、疑似异常。
- 点击 block 后展示文本、角色、置信度、过滤原因。
- 右侧显示清洗后的正文或 Markdown。

验收标准：

- 可以直观看到原图和识别框。
- 可以解释哪些内容被保留、哪些被过滤。
- 可以用于答辩展示页眉页脚去噪、双栏排序和正文重建过程。

## 阶段 6：转换质量评分模块

目标：让系统能对转换结果进行自我评估，增强产品完整度。

后端开发内容：

- 设计 `quality_score` 计算逻辑。
- 指标包括：
  - OCR 平均置信度
  - 低置信度 block 数
  - 需要复核页面数
  - 噪音过滤率
  - 复杂版面页面数
  - 空白页/低质量图片数
- 可先写入 `task_steps.summary_json` 或后续扩展 `document_texts/quality_reports`。

前端开发内容：

- 质量评分卡片。
- 异常页提示。
- 低置信度提示。

验收标准：

- 每个任务有一个 0-100 的质量评分。
- 前端能展示评分原因。
- 可以提示哪些页面建议人工检查。

## 阶段 7：AI 阅读卡片模块

目标：在清洗后的正文基础上生成结构化导读。

后端开发内容：

- 新增 `ai_reading` 模块。
- 输入 `clean/document.json`。
- 生成：
  - 一句话概括
  - 200 字核心摘要
  - 3-5 个关键词
  - 文章结构
  - 精读建议
  - 快速浏览版
  - 思考问题
- 写回 `clean/document.json` 或单独写入 `clean/reading_card.json`。
- 更新 `task_steps(ai_reading)`。

前端开发内容：

- AI 阅读卡片展示。
- 关键词标签。
- 摘要与文章结构展示。

验收标准：

- AI 只基于清洗后正文生成，不直接读取原始 OCR 噪音。
- 生成结果能展示在任务详情页。
- 导出文件中可以包含摘要和关键词。

## 阶段 8：扩展增强模块

目标：根据时间选择性做加分项。

可选模块：

- 图表导读与缩略图保留。
- 电子阅读器适配模式。
- 本地隐私模式。
- 人工校正闭环。
- 批量处理。
- 历史任务清理。

建议优先级：

| 模块 | 建议优先级 | 原因 |
| --- | --- | --- |
| 电子阅读器适配模式 | P2 | 与 EPUB 输出强相关，开发成本较低 |
| 图表缩略图保留 | P2 | 对杂志类材料效果明显 |
| 本地隐私模式 | P2 | 主要是配置和开关，适合答辩说明 |
| 人工校正闭环 | P2 | 价值高，但前后端复杂度也高 |
| 批量处理 | P2 | 可展示工程能力，但不是主线 |

## 4. 模块依赖关系

```text
数据库基础
  ↓
任务 API
  ↓
上传 API
  ↓
Celery Worker
  ↓
核心处理模块接入
  ↓
导出 API
  ↓
前端任务列表与进度
  ↓
页面预览与清洗解释
  ↓
质量评分
  ↓
AI 阅读卡片
  ↓
人工校正和其他增强
```

核心处理链路依赖：

```text
render
  ↓
layout_detect
  ↓
layout_refine
  ↓
ocr
  ↓
text_cleaning
  ↓
document_build
  ↓
export
```

## 5. 推荐接口清单

### 5.1 任务接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/tasks/upload` | 上传文件并创建任务 |
| GET | `/api/tasks` | 查询任务列表 |
| GET | `/api/tasks/{task_id}` | 查询任务详情 |
| GET | `/api/tasks/{task_id}/steps` | 查询任务阶段 |
| POST | `/api/tasks/{task_id}/retry` | 重试失败任务 |
| POST | `/api/tasks/{task_id}/cancel` | 取消任务 |

### 5.2 页面与预览接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/tasks/{task_id}/pages` | 查询页面列表 |
| GET | `/api/tasks/{task_id}/pages/{page_no}` | 查询页面详情 |
| GET | `/api/tasks/{task_id}/pages/{page_no}/image` | 获取页面图片 |
| GET | `/api/tasks/{task_id}/pages/{page_no}/layout` | 获取 layout JSON |
| GET | `/api/tasks/{task_id}/pages/{page_no}/ocr` | 获取 OCR JSON |
| GET | `/api/tasks/{task_id}/clean-document` | 获取清洗后文档结构 |

### 5.3 导出接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/tasks/{task_id}/exports` | 查询导出文件 |
| GET | `/api/exports/{export_id}/download` | 下载导出文件 |
| POST | `/api/tasks/{task_id}/exports/regenerate` | 重新生成导出文件 |

### 5.4 进度推送接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| WS | `/ws/tasks/{task_id}` | WebSocket 推送任务进度 |
| GET | `/api/tasks/{task_id}/events` | SSE 进度推送备选方案 |

第一版可以先用轮询 `GET /api/tasks/{task_id}` 和 `GET /api/tasks/{task_id}/steps`，等核心闭环稳定后再做 WebSocket 或 SSE。

## 6. 前端页面规划

### 6.1 第一阶段页面

| 页面 | 功能 |
| --- | --- |
| 上传页 | 上传 PDF/图片，选择导出格式 |
| 任务列表页 | 查看历史任务和状态 |
| 任务详情页 | 展示处理进度、失败原因、下载入口 |

### 6.2 第二阶段页面

| 页面 | 功能 |
| --- | --- |
| 页面预览页 | 查看页面图片和页面质量 |
| 清洗解释页 | 展示 layout/OCR block 和清洗原因 |
| 文档预览页 | 展示 Markdown 或结构化正文 |
| 质量报告页 | 展示转换质量评分和异常页 |

### 6.3 第三阶段页面

| 页面 | 功能 |
| --- | --- |
| AI 阅读卡片页 | 展示摘要、关键词、文章结构和思考问题 |
| 人工校正页 | 编辑 OCR 文本、恢复区块、重新导出 |
| 系统设置页 | 配置本地隐私模式、AI 开关、导出偏好 |

## 7. 开发优先级总表

| 阶段 | 模块 | 优先级 | 目标 |
| --- | --- | --- | --- |
| 0 | 基础设施 | P0 | 项目能启动，数据库和队列能连接 |
| 1 | 数据库与任务模型 | P0 | 任务状态有统一来源 |
| 2 | 上传与任务创建 | P0 | 用户能创建任务 |
| 3 | Worker 流水线 | P0 | 后端能自动完成 OCR 转换 |
| 4 | 前端进度与下载 | P0 | 完成最小可用闭环 |
| 5 | 页面预览与清洗解释 | P1 | 强化答辩展示效果 |
| 6 | 转换质量评分 | P1 | 提升系统完整度 |
| 7 | AI 阅读卡片 | P1 | 完成 AI 导读亮点 |
| 8 | 扩展增强 | P2 | 根据时间选择加分项 |

## 8. 风险与控制策略

| 风险 | 影响 | 控制策略 |
| --- | --- | --- |
| OCR/PP-DocLayout 模型加载慢 | Worker 首次任务耗时长 | Worker 启动后预热模型，或在演示前先跑一次 |
| MySQL、Redis、Worker 同时接入复杂 | 初期开发成本上升 | 先完成数据库任务表，再接 Celery，前端先轮询 |
| 复杂杂志页面识别不稳定 | 影响最终效果 | 保留页面预览和调试 JSON，优先展示处理效果较好的样例 |
| AI 导读接口成本或速度不稳定 | 演示不稳定 | AI 导读放 P1，支持关闭或使用缓存结果 |
| 前端预览交互复杂 | 开发时间不确定 | 先做只读预览，再做点击联动和人工校正 |
| 导出 EPUB 样式兼容问题 | 阅读器显示不一致 | 第一版使用简洁样式，后续增加阅读器适配模式 |

## 9. 第一轮开发建议

下一轮建议从后端基础设施开始，不直接做前端大页面。

推荐顺序：

1. 建立 FastAPI 应用入口。
2. 建立 MySQL 连接和 SQLAlchemy ORM。
3. 实现 `tasks`、`task_steps` 两张表的读写。
4. 实现上传接口并创建任务目录。
5. 接入 Celery，把已有 `pipeline.task_runner` 挂到 Worker。
6. 前端再对接任务列表、任务详情和下载。

这个顺序的理由是：任务状态和异步处理是整个系统的骨架。骨架稳定后，前端页面、清洗预览、质量评分、AI 阅读卡片都可以逐步挂上去。

## 10. 阶段性交付物

| 阶段 | 交付物 |
| --- | --- |
| 阶段 1 | 数据库 ORM、任务服务、任务查询接口 |
| 阶段 2 | 文件上传接口、任务目录创建、输入文件记录 |
| 阶段 3 | Celery Worker、后端处理流水线、阶段状态更新 |
| 阶段 4 | React 上传页、任务列表页、任务详情页、下载功能 |
| 阶段 5 | 页面预览、layout/OCR 框叠加、清洗解释 |
| 阶段 6 | 质量评分报告 |
| 阶段 7 | AI 阅读卡片 |
| 阶段 8 | 图表导读、阅读器适配、人工校正等增强功能 |

## 11. 验收主线

最终演示应至少覆盖：

1. 上传一份扫描 PDF 或图片。
2. 创建任务并进入处理队列。
3. 展示任务阶段进度。
4. 自动完成页面渲染、版面分析、OCR、文本清洗、导出。
5. 下载 Markdown 或 EPUB。
6. 展示页面预览和识别框。
7. 展示清洗前后对比。
8. 展示质量评分。
9. 展示 AI 阅读卡片。

第一版最小验收可以只覆盖 1-5；课程展示版本建议覆盖 1-9。
