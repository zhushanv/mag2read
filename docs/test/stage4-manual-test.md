# 阶段 4 手动测试文档：前端上传、任务进度与导出下载

## 1. 测试目标

验证阶段 4 的核心闭环：

- 前端页面可以打开并展示 Mag2Read 首页。
- 可以上传 PDF/JPG/PNG，创建转换任务。
- 前端可以轮询任务状态、步骤状态、文件列表和导出记录。
- 任务完成后可以通过导出记录下载文件。

## 2. 启动服务

### 2.1 后端 API

在项目根目录执行：

```bash
conda run -n industrial-cv uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

### 2.2 Celery Worker

另开一个终端，在项目根目录执行：

```bash
conda run -n industrial-cv celery -A backend.app.workers.celery_app worker --loglevel=info
```

### 2.3 前端

在 `UI` 目录执行：

```bash
npm install
npm run dev
```

浏览器访问：

```text
http://127.0.0.1:5173
```

## 3. API 快速验证

### 3.1 健康检查

```bash
curl http://127.0.0.1:8000/api/health
```

预期：返回 `status` 为健康状态。

### 3.2 查看任务列表

```bash
curl http://127.0.0.1:8000/api/tasks
```

预期：返回数组。没有任务时为空数组。

### 3.3 上传测试文件

```bash
curl -X POST http://127.0.0.1:8000/api/tasks/upload \
  -F "file=@pdfs/pdf1.0.pdf" \
  -F "output_format=epub,markdown" \
  -F "auto_start=true"
```

记录返回结果中的 `task_id`。

### 3.4 查看步骤状态

```bash
curl http://127.0.0.1:8000/api/tasks/<task_id>/steps
```

预期：随着 Worker 执行，能看到 `render`、`layout_detect`、`ocr`、`export` 等步骤记录。

### 3.5 查看导出记录

```bash
curl http://127.0.0.1:8000/api/tasks/<task_id>/exports
```

预期：任务完成后返回导出文件记录，包含 `id`、`format`、`file_size`、`status`。

### 3.6 下载导出文件

```bash
curl -L -o output.epub http://127.0.0.1:8000/api/exports/<export_id>/download
```

预期：当前目录生成 `output.epub`，文件大小不为 0。

## 4. 前端手动测试步骤

1. 打开 `http://127.0.0.1:5173`。
2. 确认首页出现上传区域、格式选择按钮、高级选项和最近转换记录。
3. 上传 `pdfs/pdf1.0.pdf`，选择 `EPUB` 和 `Markdown`。
4. 点击“开始转换”。
5. 确认页面进入任务详情，顶部整体进度会变化。
6. 确认步骤条能显示“版面分析 / 文字识别 / 文本整理 / 文件导出”的状态。
7. 任务完成后，确认进入完成页。
8. 点击导出文件按钮，确认浏览器可以下载文件。
9. 点击“返回首页”，确认回到上传页，最近转换记录中出现该任务。

## 5. 异常情况检查

- 如果首页提示 `Failed to fetch`：检查后端 API 是否运行在 `127.0.0.1:8000`。
- 如果任务一直停在 `pending`：检查 Celery Worker 是否启动，Redis 是否可用。
- 如果完成页没有导出文件：调用 `/api/tasks/<task_id>/exports` 检查数据库是否已有导出记录。
- 如果下载返回 404：检查 `export_records.file_path` 指向的文件是否真实存在。
- 如果 OCR 首次运行很慢：通常是模型首次下载或初始化耗时，观察 Worker 日志中的 OCR timing 信息。

## 6. 本阶段新增文件

- `UI/package.json`
- `UI/src/App.tsx`
- `UI/src/styles.css`
- `backend/app/api/exports.py`

## 7. 当前边界

AI 导读面板目前是前端交互入口，尚未接入真实大模型 API。后续阶段接入 AI 导读服务后，可以复用当前面板结构。
