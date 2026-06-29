# 阶段 5 手动测试文档：页面预览与可解释清洗

## 1. 测试目标

验证阶段 5 的展示闭环：

- 后端可以返回任务页面列表、页面图片、layout JSON、OCR JSON 和清洗后文档。
- 前端任务详情页可以显示真实页面图片。
- 页面图片上可以叠加识别框，并按标题、正文、图注、表格、过滤内容区分颜色。
- 点击识别框后，可以查看文本、角色、置信度和过滤原因。
- 右侧可以展示清洗后的正文预览。

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

## 3. 准备测试任务

可以继续使用阶段 4 的上传流程，也可以直接用 curl 创建一个新任务：

```bash
curl -X POST http://127.0.0.1:8000/api/tasks/upload \
  -F "file=@pdfs/pdf1.0.pdf" \
  -F "output_format=epub,markdown" \
  -F "auto_start=true"
```

记录返回结果中的 `task_id`。等待任务至少完成 `layout_refine` 和 `ocr` 阶段；如果要验证右侧清洗正文，需要等 `text_cleaning` 阶段完成。

## 4. API 快速验证

### 4.1 查看页面列表

```bash
curl http://127.0.0.1:8000/api/tasks/<task_id>/pages
```

预期：返回页面数组，包含 `page_no`、`image_path`、`width`、`height`、`quality_status`、`need_review` 等字段。

### 4.2 查看单页详情

```bash
curl http://127.0.0.1:8000/api/tasks/<task_id>/pages/1
```

预期：返回第 1 页页面记录。

### 4.3 获取页面图片

```bash
curl -L -o page_001.png http://127.0.0.1:8000/api/tasks/<task_id>/pages/1/image
```

预期：当前目录生成 `page_001.png`，文件可以正常打开。

### 4.4 获取 layout JSON

```bash
curl http://127.0.0.1:8000/api/tasks/<task_id>/pages/1/layout
```

预期：返回 `blocks` 列表，每个 block 包含 `bbox`、`role`、`is_noise`、`order` 等字段。

### 4.5 获取 OCR JSON

```bash
curl http://127.0.0.1:8000/api/tasks/<task_id>/pages/1/ocr
```

预期：返回 `blocks` 列表，包含 OCR 文本、置信度和行数信息。

### 4.6 获取清洗后文档

```bash
curl http://127.0.0.1:8000/api/tasks/<task_id>/clean-document
```

预期：返回清洗后的文档结构，包含页面和正文 block。

## 5. 前端手动测试步骤

1. 打开 `http://127.0.0.1:5173`。
2. 上传 `pdfs/pdf1.0.pdf`，或从最近转换记录中进入一个已有任务。
3. 在任务详情页查看“页面预览与版面分析”区域。
4. 确认左侧页面列表显示页码和质量状态。
5. 点击不同页码，确认中间页面图片随之切换。
6. 等 `layout_refine` 或 `ocr` 阶段完成后，确认页面图片上出现识别框。
7. 观察识别框颜色：标题、正文、图注/图片、表格、过滤内容应有明显区分。
8. 点击任意识别框，确认下方显示角色、置信度、保留/过滤状态和 OCR 文本。
9. 等 `text_cleaning` 阶段完成后，查看右侧“清洗后文本”，确认正文内容会替换原来的等待提示。
10. 任务完成后，确认阶段 4 的下载区域仍可正常使用。

## 6. 异常情况检查

- 页面列表为空：确认 Worker 是否已经完成 `render` 阶段，并检查 `task_pages` 表是否有记录。
- 页面图片 404：检查 `backend/storage/tasks/<task_id>/pages/page_001.png` 是否存在。
- layout 接口 404：说明 `layout_refine` 阶段尚未完成，等待 Worker 继续执行。
- OCR 接口 404：说明 `ocr` 阶段尚未完成，或 OCR 阶段失败。
- 右侧没有清洗正文：确认 `backend/storage/tasks/<task_id>/clean/document.json` 是否存在。
- 识别框位置明显偏移：检查 layout/OCR JSON 中的 `width`、`height` 是否与页面图片尺寸一致。

## 7. 本阶段新增或修改内容

- 新增页面预览接口：
  - `GET /api/tasks/{task_id}/pages`
  - `GET /api/tasks/{task_id}/pages/{page_no}`
  - `GET /api/tasks/{task_id}/pages/{page_no}/image`
  - `GET /api/tasks/{task_id}/pages/{page_no}/layout`
  - `GET /api/tasks/{task_id}/pages/{page_no}/ocr`
  - `GET /api/tasks/{task_id}/clean-document`
- 前端任务详情页新增真实页面图片、识别框叠加、block 信息面板和清洗正文预览。

## 8. 当前边界

本阶段是只读预览版本。前端可以解释清洗结果，但暂不支持人工编辑 OCR 文本、恢复误删 block 或重新导出。人工校正闭环放到后续增强阶段处理。
