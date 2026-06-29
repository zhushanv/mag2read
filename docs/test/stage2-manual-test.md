# 阶段 2 手动测试文档

## 1. 测试目标

阶段 2 的目标是验证“文件上传与任务创建模块”。

本阶段只测试：

- `POST /api/tasks/upload` 可以接收 PDF/JPG/PNG。
- 上传后可以创建 `tasks` 记录。
- 上传后可以创建 `task_files` 记录。
- 原始文件可以保存到任务目录 `input/`。
- 可以通过任务 API 查询上传后的任务。
- 可以通过文件 API 查询上传文件记录。

本阶段不测试：

- Celery Worker 自动处理。
- PDF 页面渲染。
- OCR。
- 文本清洗。
- EPUB 导出。

因此，阶段 2 上传成功后，任务状态仍然是：

```text
pending
```

真正自动进入处理流水线是在阶段 3。

## 2. 涉及文件

阶段 2 主要修改：

```text
backend/app/api/tasks.py
backend/app/core/config.py
backend/app/schemas/task.py
backend/app/services/task_service.py
.env.example
```

阶段 2 新增或使用的接口：

```text
POST /api/tasks/upload
GET  /api/tasks/{task_id}/files
```

## 3. 前置条件

进入项目目录：

```bash
cd /Users/zhu/projects/python-project/课程项目2
```

确认 `.env` 中配置了 MySQL：

```text
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=你的MySQL密码
MYSQL_DATABASE=mag2read
MAX_UPLOAD_SIZE_MB=100
```

确认 MySQL 已启动，并已经执行过：

```bash
mysql -u root -p < backend/database/init_mysql.sql
```

## 4. 启动 FastAPI

```bash
conda run -n industrial-cv uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

浏览器打开：

```text
http://127.0.0.1:8000/docs
```

预期结果：

- 能看到 `tasks` 分组。
- 能看到 `POST /api/tasks/upload`。
- 能看到 `GET /api/tasks/{task_id}/files`。

## 5. 上传 JPG 测试

新开终端执行：

```bash
curl -X POST http://127.0.0.1:8000/api/tasks/upload \
  -F "file=@pdfs/poet.jpg" \
  -F "task_id=manual_stage2_image" \
  -F "output_format=markdown,epub"
```

预期返回：

```json
{
  "task_id": "manual_stage2_image",
  "original_name": "poet.jpg",
  "input_type": "image",
  "status": "pending",
  "progress": 0
}
```

检查文件是否保存：

```bash
ls backend/storage/tasks/manual_stage2_image/input
```

预期结果：

```text
poet.jpg
```

## 6. 上传 PDF 测试

执行：

```bash
curl -X POST http://127.0.0.1:8000/api/tasks/upload \
  -F "file=@pdfs/pdf1.0.pdf" \
  -F "task_id=manual_stage2_pdf" \
  -F "output_format=markdown,epub"
```

预期返回：

```json
{
  "task_id": "manual_stage2_pdf",
  "original_name": "pdf1.0.pdf",
  "input_type": "pdf",
  "status": "pending",
  "progress": 0
}
```

检查文件是否保存：

```bash
ls backend/storage/tasks/manual_stage2_pdf/input
```

预期结果：

```text
pdf1.0.pdf
```

## 7. 查询任务详情

执行：

```bash
curl http://127.0.0.1:8000/api/tasks/manual_stage2_image
```

预期重点字段：

```json
{
  "task_id": "manual_stage2_image",
  "original_name": "poet.jpg",
  "input_type": "image",
  "status": "pending",
  "storage_dir": "/Users/zhu/projects/python-project/课程项目2/backend/storage/tasks/manual_stage2_image"
}
```

## 8. 查询任务文件记录

执行：

```bash
curl http://127.0.0.1:8000/api/tasks/manual_stage2_image/files
```

预期结果：

```json
[
  {
    "task_id": "manual_stage2_image",
    "file_role": "input_image",
    "file_name": "poet.jpg",
    "file_path": "/Users/zhu/projects/python-project/课程项目2/backend/storage/tasks/manual_stage2_image/input/poet.jpg",
    "mime_type": "image/jpeg",
    "file_size": 155647
  }
]
```

PDF 任务对应：

```bash
curl http://127.0.0.1:8000/api/tasks/manual_stage2_pdf/files
```

预期 `file_role`：

```text
input_pdf
```

## 9. 查询任务列表

执行：

```bash
curl http://127.0.0.1:8000/api/tasks
```

预期可以看到：

```text
manual_stage2_image
manual_stage2_pdf
```

## 10. 在 MySQL 中检查

进入 MySQL：

```bash
mysql -u root -p
```

执行：

```sql
USE mag2read;

SELECT task_id, original_name, input_type, status, progress, storage_dir
FROM tasks
WHERE task_id IN ('manual_stage2_image', 'manual_stage2_pdf');

SELECT task_id, file_role, file_name, file_path, file_size
FROM task_files
WHERE task_id IN ('manual_stage2_image', 'manual_stage2_pdf');
```

预期结果：

```text
tasks 表中有两条任务记录
task_files 表中有两条输入文件记录
manual_stage2_image 的 file_role 是 input_image
manual_stage2_pdf 的 file_role 是 input_pdf
```

## 11. 测试不支持的文件类型

可以创建一个临时 txt：

```bash
echo "hello" > /tmp/mag2read-test.txt
```

上传：

```bash
curl -X POST http://127.0.0.1:8000/api/tasks/upload \
  -F "file=@/tmp/mag2read-test.txt" \
  -F "task_id=manual_stage2_txt"
```

预期结果：

```json
{
  "detail": "Unsupported file type. Allowed: .jpeg, .jpg, .pdf, .png"
}
```

HTTP 状态码应为：

```text
400
```

## 12. 测试重复 task_id

重复上传：

```bash
curl -X POST http://127.0.0.1:8000/api/tasks/upload \
  -F "file=@pdfs/poet.jpg" \
  -F "task_id=manual_stage2_image"
```

预期结果：

```json
{
  "detail": "Task ID already exists"
}
```

HTTP 状态码应为：

```text
409
```

## 13. 清理手动测试数据

如果需要清理数据库：

```sql
USE mag2read;
DELETE FROM tasks WHERE task_id IN ('manual_stage2_image', 'manual_stage2_pdf');
```

由于外键级联删除，相关 `task_files` 会一起删除。

如果需要清理文件：

```bash
rm -rf backend/storage/tasks/manual_stage2_image
rm -rf backend/storage/tasks/manual_stage2_pdf
```

## 14. 阶段 2 验收清单

完成以下检查即可认为阶段 2 通过：

- [ ] `POST /api/tasks/upload` 可以上传 JPG。
- [ ] `POST /api/tasks/upload` 可以上传 PDF。
- [ ] 上传后 `tasks` 表有记录。
- [ ] 上传后 `task_files` 表有记录。
- [ ] 上传后原文件保存到 `backend/storage/tasks/{task_id}/input/`。
- [ ] `GET /api/tasks/{task_id}` 可以查询任务。
- [ ] `GET /api/tasks/{task_id}/files` 可以查询输入文件。
- [ ] 不支持的文件类型返回 400。
- [ ] 重复 `task_id` 返回 409。

## 15. 常见问题

### 15.1 上传接口不存在

确认 FastAPI 已重启。

如果你使用 `--reload`，通常会自动加载；如果没有，手动重启：

```bash
conda run -n industrial-cv uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

### 15.2 上传时报 python-multipart 相关错误

安装依赖：

```bash
conda run -n industrial-cv pip install python-multipart
```

或者：

```bash
conda run -n industrial-cv pip install -r backend/requirements.txt
```

### 15.3 上传成功但文件目录不存在

检查返回结果中的 `storage_dir` 字段，然后执行：

```bash
ls 返回的storage_dir路径
```

如果 `.env` 中 `STORAGE_ROOT` 是相对路径，后端会自动按项目根目录解析。

### 15.4 上传成功但不会自动 OCR

这是阶段 2 的正常现象。

阶段 2 只完成：

```text
上传文件
  ↓
创建任务
  ↓
保存原始文件
  ↓
写入 task_files
```

自动执行：

```text
render → layout → ocr → clean → export
```

会在阶段 3 接入 Celery Worker 后完成。

## 16. 下一阶段入口

阶段 2 通过后，进入阶段 3：

```text
异步任务与处理流水线模块
```

阶段 3 要实现：

- Celery 任务入口。
- 上传后投递后台任务。
- Worker 调用 `pipeline.task_runner`。
- 每个阶段写入 `task_steps`。
- 成功或失败时同步更新 `tasks`。
