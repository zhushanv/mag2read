# 阶段 3 手动测试文档

## 1. 测试目标

阶段 3 的目标是验证“异步任务与处理流水线模块”。

本阶段需要手动确认：

- 上传文件后可以自动投递 Celery 任务。
- Celery Worker 可以接收 `pipeline.process_uploaded_task`。
- Worker 可以按阶段执行：
  - `render`
  - `layout_detect`
  - `layout_refine`
  - `ocr`
  - `text_cleaning`
  - `document_build`
  - `export`
- 每个阶段可以写入 `task_steps`。
- `tasks` 主表会同步更新 `status/current_stage/progress`。
- 处理成功后任务状态变为 `success`。
- 处理失败后任务状态变为 `failed`，并记录错误信息。

本阶段不要求做完整压力测试，也不要求覆盖所有 PDF 样例。

## 2. 涉及文件

阶段 3 主要修改：

```text
backend/app/modules/render.py
backend/app/api/tasks.py
backend/app/services/task_service.py
backend/app/workers/tasks.py
docs/test/stage3-manual-test.md
```

核心 Celery 任务：

```text
pipeline.process_uploaded_task
```

## 3. 前置条件

进入项目目录：

```bash
cd /Users/zhu/projects/python-project/课程项目2
```

确认 `.env` 配置正确：

```text
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=你的MySQL密码
MYSQL_DATABASE=mag2read

REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
```

确认已经初始化数据库：

```bash
mysql -u root -p < backend/database/init_mysql.sql
```

确认 Redis 正常：

```bash
redis-cli ping
```

预期：

```text
PONG
```

## 4. 启动 FastAPI

终端 1：

```bash
conda run -n industrial-cv uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

检查健康接口：

```bash
curl http://127.0.0.1:8000/api/health
```

预期：

```text
database.ok = true
redis.ok = true
```

## 5. 启动 Celery Worker

终端 2：

```bash
conda run -n industrial-cv celery -A backend.app.workers.celery_app.celery_app worker --loglevel=info --concurrency=1
```

预期日志中能看到任务：

```text
stage0.ping
pipeline.process_uploaded_task
```

说明：

- `--concurrency=1` 是推荐设置。
- PaddleOCR/PP-DocLayout 比较占内存，第一版不要开高并发。

## 6. 先测试 Celery Ping

终端 3：

```bash
conda run -n industrial-cv python -c "from backend.app.workers.tasks import ping; r = ping.delay(); print(r.get(timeout=10))"
```

预期：

```text
pong
```

如果这里失败，先不要测 OCR 流水线，优先检查 Redis 和 Worker。

## 7. 上传图片并自动启动后台任务

建议先用单张图片测试，速度比 PDF 快。

终端 3：

```bash
curl -X POST http://127.0.0.1:8000/api/tasks/upload \
  -F "file=@pdfs/poet.jpg" \
  -F "task_id=manual_stage3_image" \
  -F "output_format=markdown,epub" \
  -F "auto_start=true"
```

预期上传接口立即返回：

```json
{
  "task_id": "manual_stage3_image",
  "status": "pending"
}
```

注意：

- 上传接口返回时任务可能还是 `pending`。
- Celery Worker 会在后台继续处理。
- 需要看 Worker 终端日志和任务状态接口。

## 8. 查询任务状态

反复执行：

```bash
curl http://127.0.0.1:8000/api/tasks/manual_stage3_image
```

可能看到的状态变化：

```text
pending
processing
success
failed
```

处理中时可能看到：

```json
{
  "task_id": "manual_stage3_image",
  "status": "processing",
  "current_stage": "ocr",
  "progress": 65
}
```

成功后预期：

```json
{
  "task_id": "manual_stage3_image",
  "status": "success",
  "current_stage": null,
  "progress": 100
}
```

## 9. 查询任务步骤

执行：

```bash
curl http://127.0.0.1:8000/api/tasks/manual_stage3_image/steps
```

成功时应看到类似阶段：

```text
render
layout_detect
layout_refine
ocr
text_cleaning
document_build
export
```

每个阶段预期字段：

```json
{
  "stage": "render",
  "status": "success",
  "progress": 100,
  "duration_ms": 1234,
  "summary_json": {}
}
```

如果某一步失败：

```json
{
  "stage": "ocr",
  "status": "failed",
  "error_message": "..."
}
```

同时：

```bash
curl http://127.0.0.1:8000/api/tasks/manual_stage3_image
```

应看到：

```text
status = failed
current_stage = 失败阶段
error_message = 错误信息
```

## 10. 查询文件记录

执行：

```bash
curl http://127.0.0.1:8000/api/tasks/manual_stage3_image/files
```

预期至少能看到：

```text
input_image
page_image
layout_raw_json
layout_json
ocr_json
clean_json
cleaning_report
markdown
epub
```

说明：

- `markdown` 来自 `document_build`。
- `epub` 来自 `export`。
- 如果 `output_format` 包含 `docx/html/txt`，也会有对应导出记录。

## 11. 检查任务目录

执行：

```bash
find backend/storage/tasks/manual_stage3_image -maxdepth 2 -type f | sort
```

预期目录结构类似：

```text
backend/storage/tasks/manual_stage3_image/input/poet.jpg
backend/storage/tasks/manual_stage3_image/pages/page_001.png
backend/storage/tasks/manual_stage3_image/layout_raw/page_001.json
backend/storage/tasks/manual_stage3_image/layout/page_001.json
backend/storage/tasks/manual_stage3_image/ocr/page_001.json
backend/storage/tasks/manual_stage3_image/clean/document.json
backend/storage/tasks/manual_stage3_image/clean/book.md
backend/storage/tasks/manual_stage3_image/output/manual_stage3_image.epub
```

实际文件数量取决于版面分析和导出结果。

## 12. MySQL 检查

进入 MySQL：

```bash
mysql -u root -p
```

执行：

```sql
USE mag2read;

SELECT task_id, status, current_stage, progress, error_message
FROM tasks
WHERE task_id = 'manual_stage3_image';

SELECT stage, status, progress, duration_ms, error_message
FROM task_steps
WHERE task_id = 'manual_stage3_image'
ORDER BY id;

SELECT file_role, file_name, page_no
FROM task_files
WHERE task_id = 'manual_stage3_image'
ORDER BY id;

SELECT format, file_path, status
FROM export_records
WHERE task_id = 'manual_stage3_image';
```

预期：

- `tasks.status = success`
- `tasks.progress = 100`
- `task_steps` 有多个阶段记录
- `task_files` 有输入文件、中间 JSON 和导出文件记录
- `export_records` 有 EPUB 记录

## 13. 测试只上传不自动启动

如果只想测试上传，不想启动 Worker：

```bash
curl -X POST http://127.0.0.1:8000/api/tasks/upload \
  -F "file=@pdfs/poet.jpg" \
  -F "task_id=manual_stage3_no_auto" \
  -F "auto_start=false"
```

预期：

```text
任务创建成功
状态保持 pending
Worker 不会自动处理
```

这个模式适合排查上传阶段问题。

## 14. 手动投递已有任务

如果一个任务已经上传，但没有自动启动，可以手动投递：

```bash
conda run -n industrial-cv python -c "from backend.app.workers.tasks import process_uploaded_task; r = process_uploaded_task.delay('manual_stage3_no_auto'); print(r.id)"
```

然后继续查询：

```bash
curl http://127.0.0.1:8000/api/tasks/manual_stage3_no_auto/steps
```

## 15. 清理测试数据

数据库清理：

```sql
USE mag2read;
DELETE FROM tasks
WHERE task_id IN ('manual_stage3_image', 'manual_stage3_no_auto');
```

文件清理：

```bash
rm -rf backend/storage/tasks/manual_stage3_image
rm -rf backend/storage/tasks/manual_stage3_no_auto
```

## 16. 阶段 3 验收清单

完成以下检查即可认为阶段 3 通过：

- [ ] Redis 正常运行。
- [ ] FastAPI 正常运行。
- [ ] Celery Worker 正常启动。
- [ ] Worker 注册了 `pipeline.process_uploaded_task`。
- [ ] 上传文件后可以自动投递任务。
- [ ] `tasks.status` 会从 `pending` 变为 `processing`。
- [ ] `task_steps` 会写入多个阶段。
- [ ] 阶段完成后 `tasks.status = success`。
- [ ] 阶段失败时 `tasks.status = failed`，并有错误信息。
- [ ] 任务目录中生成 pages/layout/ocr/clean/output 文件。
- [ ] `task_files` 有输入文件和过程文件记录。
- [ ] `export_records` 有导出文件记录。

## 17. 常见问题

### 17.1 上传成功但任务一直 pending

检查：

- Redis 是否启动。
- Celery Worker 是否启动。
- 上传时 `auto_start` 是否为 `true`。
- Worker 日志里是否收到 `pipeline.process_uploaded_task`。

### 17.2 Worker 报模型下载或模型路径错误

检查：

```text
backend/storage/paddlex_cache
```

如果模型缓存不在 active storage，而是在过程备份里，可能需要重新下载模型或把缓存放回 active storage。

### 17.3 OCR 阶段很慢

这是正常现象。PaddleOCR 首次加载模型会比较慢。

建议：

- 第一轮用单张图片测试。
- Worker 使用 `--concurrency=1`。
- 演示前先跑一次，让模型完成预热。

### 17.4 `markdown` 不出现在 export_records

当前设计中：

- Markdown 由 `document_build` 生成，记录在 `task_files`。
- `export_records` 主要记录 `epub/docx/html/txt`。

所以 Markdown 不一定出现在 `export_records`，但应该出现在：

```bash
curl http://127.0.0.1:8000/api/tasks/{task_id}/files
```

### 17.5 任务失败后重新上传同一个 task_id 报 409

因为 `task_id` 唯一。

处理方式：

- 换一个新的 `task_id`。
- 或清理旧任务：

```sql
DELETE FROM tasks WHERE task_id = 'manual_stage3_image';
```

并删除对应任务目录。

## 18. 下一阶段入口

阶段 3 通过后，进入阶段 4：

```text
前端任务进度与下载闭环
```

阶段 4 要实现：

- 任务列表页。
- 任务详情页。
- 阶段进度条。
- 成功/失败状态展示。
- 导出文件下载区。
