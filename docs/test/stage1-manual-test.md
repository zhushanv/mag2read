# 阶段 1 手动测试文档

## 1. 测试目标

阶段 1 的目标是验证“任务与数据库基础模块”是否可用。

本阶段只测试：

- SQLAlchemy ORM 模型能被导入。
- FastAPI 能加载任务 API。
- 可以手动创建任务记录。
- 可以查询任务列表。
- 可以查询单个任务详情。
- 可以创建或更新任务步骤。
- 可以查询任务步骤列表。

本阶段不测试：

- 文件上传。
- Celery 自动处理。
- OCR 完整流水线。
- 前端页面。

## 2. 涉及文件

阶段 1 新增或修改的主要文件：

```text
backend/app/models/task.py
backend/app/models/__init__.py
backend/app/schemas/task.py
backend/app/schemas/__init__.py
backend/app/services/enums.py
backend/app/services/task_service.py
backend/app/api/tasks.py
backend/app/main.py
```

依赖阶段 0 文件：

```text
.env
backend/app/core/config.py
backend/app/core/database.py
backend/database/init_mysql.sql
```

## 3. 前置条件

进入项目目录：

```bash
cd /Users/zhu/projects/python-project/课程项目2
```

确认已经创建 `.env`：

```bash
ls .env
```

`.env` 中至少包含：

```text
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=你的MySQL密码
MYSQL_DATABASE=mag2read
```

确认 MySQL 已启动，并且已经执行过：

```bash
mysql -u root -p < backend/database/init_mysql.sql
```

## 4. 启动 FastAPI

```bash
conda run -n industrial-cv uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

如果你已经进入 `industrial-cv` 环境，也可以执行：

```bash
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

浏览器打开：

```text
http://127.0.0.1:8000/docs
```

预期结果：

- 能看到 Swagger API 页面。
- 页面中出现 `tasks` 分组。
- 页面中出现 `health` 分组。

## 5. 测试健康检查

新开终端执行：

```bash
curl http://127.0.0.1:8000/api/health
```

预期结果：

```json
{
  "status": "ok",
  "services": {
    "api": {
      "ok": true
    },
    "database": {
      "ok": true
    }
  }
}
```

如果 Redis 没启动，`status` 可能是 `degraded`。阶段 1 主要依赖 MySQL，只要 `database.ok = true` 即可继续。

## 6. 手动创建任务

执行：

```bash
curl -X POST http://127.0.0.1:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "manual_stage1_task",
    "original_name": "stage1-demo.pdf",
    "input_type": "pdf",
    "output_format": "markdown,epub",
    "page_count": 0
  }'
```

预期结果：

```json
{
  "task_id": "manual_stage1_task",
  "original_name": "stage1-demo.pdf",
  "input_type": "pdf",
  "status": "pending",
  "current_stage": null,
  "progress": 0
}
```

说明：

- `task_id` 可以不传，不传时后端会自动生成。
- 这里传固定值是为了后续测试方便。

## 7. 查询任务列表

执行：

```bash
curl http://127.0.0.1:8000/api/tasks
```

预期结果：

```json
[
  {
    "task_id": "manual_stage1_task",
    "status": "pending"
  }
]
```

实际返回字段会更多，包括：

- `id`
- `task_id`
- `original_name`
- `input_type`
- `status`
- `progress`
- `storage_dir`
- `created_at`
- `updated_at`

## 8. 查询单个任务详情

执行：

```bash
curl http://127.0.0.1:8000/api/tasks/manual_stage1_task
```

预期结果：

```json
{
  "task_id": "manual_stage1_task",
  "original_name": "stage1-demo.pdf",
  "status": "pending",
  "progress": 0
}
```

## 9. 更新任务状态

执行：

```bash
curl -X PATCH http://127.0.0.1:8000/api/tasks/manual_stage1_task \
  -H "Content-Type: application/json" \
  -d '{
    "status": "processing",
    "current_stage": "render",
    "progress": 10
  }'
```

预期结果：

```json
{
  "task_id": "manual_stage1_task",
  "status": "processing",
  "current_stage": "render",
  "progress": 10
}
```

## 10. 创建或更新任务步骤

执行：

```bash
curl -X PUT http://127.0.0.1:8000/api/tasks/manual_stage1_task/steps \
  -H "Content-Type: application/json" \
  -d '{
    "stage": "render",
    "status": "processing",
    "progress": 50,
    "summary_json": {
      "message": "manual stage1 step test"
    }
  }'
```

预期结果：

```json
{
  "task_id": "manual_stage1_task",
  "stage": "render",
  "status": "processing",
  "progress": 50,
  "summary_json": {
    "message": "manual stage1 step test"
  }
}
```

再次执行同一个接口，但改成成功：

```bash
curl -X PUT http://127.0.0.1:8000/api/tasks/manual_stage1_task/steps \
  -H "Content-Type: application/json" \
  -d '{
    "stage": "render",
    "status": "success",
    "progress": 100,
    "duration_ms": 1200,
    "summary_json": {
      "rendered_page_count": 0
    }
  }'
```

预期结果：

```json
{
  "stage": "render",
  "status": "success",
  "progress": 100,
  "duration_ms": 1200
}
```

说明：这是 upsert 接口，同一个 `task_id + stage` 会更新原记录，不会重复插入。

## 11. 查询任务步骤列表

执行：

```bash
curl http://127.0.0.1:8000/api/tasks/manual_stage1_task/steps
```

预期结果：

```json
[
  {
    "task_id": "manual_stage1_task",
    "stage": "render",
    "status": "success",
    "progress": 100
  }
]
```

## 12. 直接在 MySQL 中检查

进入 MySQL：

```bash
mysql -u root -p
```

执行：

```sql
USE mag2read;

SELECT task_id, original_name, status, current_stage, progress
FROM tasks
WHERE task_id = 'manual_stage1_task';

SELECT task_id, stage, status, progress, summary_json
FROM task_steps
WHERE task_id = 'manual_stage1_task';
```

预期结果：

```text
tasks 中存在 manual_stage1_task
task_steps 中存在 render 阶段记录
```

## 13. 清理手动测试数据

如果需要清理：

```sql
USE mag2read;
DELETE FROM tasks WHERE task_id = 'manual_stage1_task';
```

由于表之间有外键级联删除，相关 `task_steps` 也会一起删除。

## 14. 阶段 1 验收清单

完成以下检查即可认为阶段 1 基础模块通过：

- [ ] FastAPI 可以启动。
- [ ] `/docs` 中出现 `tasks` API 分组。
- [ ] `POST /api/tasks` 可以创建任务。
- [ ] `GET /api/tasks` 可以查询任务列表。
- [ ] `GET /api/tasks/{task_id}` 可以查询任务详情。
- [ ] `PATCH /api/tasks/{task_id}` 可以更新任务状态。
- [ ] `PUT /api/tasks/{task_id}/steps` 可以创建或更新阶段记录。
- [ ] `GET /api/tasks/{task_id}/steps` 可以查询阶段记录。
- [ ] MySQL 中 `tasks` 和 `task_steps` 表能看到对应数据。

## 15. 常见问题

### 15.1 创建任务时报 500

优先检查：

- `.env` 中 MySQL 密码是否正确。
- 是否执行过 `backend/database/init_mysql.sql`。
- MySQL 中是否存在 `mag2read` 数据库。

### 15.2 创建同一个 task_id 报错

`tasks.task_id` 是唯一字段。同一个 `task_id` 只能创建一次。

处理方式：

- 换一个 `task_id`。
- 或先删除测试数据：

```sql
DELETE FROM tasks WHERE task_id = 'manual_stage1_task';
```

### 15.3 current_stage 校验失败

`current_stage` 只能使用预定义阶段：

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

### 15.4 status 校验失败

`status` 只能使用：

```text
pending
processing
success
failed
cancelled
skipped
```

## 16. 下一阶段入口

阶段 1 通过后，进入阶段 2：

```text
文件上传与任务创建模块
```

阶段 2 会把 `POST /api/tasks` 扩展为真正的上传接口：

```text
POST /api/tasks/upload
```

并完成：

- 文件类型校验。
- 文件大小校验。
- 创建任务目录。
- 保存原始文件。
- 写入 `task_files`。
- 投递 Celery 任务。
