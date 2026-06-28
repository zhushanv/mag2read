# Celery Worker 技术解释文档

## 1. Celery Worker 是什么

Celery Worker 可以理解为“后台任务执行进程”。

在普通 Web 系统中，用户请求通常是这样处理的：

```text
用户点击按钮
  ↓
前端发送 HTTP 请求
  ↓
FastAPI 接收请求
  ↓
FastAPI 立即处理并返回结果
```

这种方式适合处理很快完成的任务，例如查询任务列表、获取用户信息、下载文件。

但是 OCR 项目里有很多耗时任务：

- PDF 渲染成图片。
- 图像质量检查。
- PP-DocLayout 版面分析。
- PaddleOCR 文字识别。
- 文本清洗。
- EPUB / DOCX / Markdown 导出。
- AI 导读生成。

这些任务可能持续几十秒甚至几分钟。如果直接放在 FastAPI 请求里执行，会出现几个问题：

- 浏览器请求长时间等待。
- FastAPI 接口被阻塞。
- 多个用户同时上传时服务容易卡死。
- 任务失败后不好重试。
- 前端很难实时获取阶段进度。

所以需要把这些耗时任务交给 Celery Worker。

整体结构变成：

```text
FastAPI 负责接收请求
Celery Worker 负责后台干活
Redis 负责传递任务
MySQL 负责保存任务状态
```

## 2. 为什么不是 FastAPI 自己处理

FastAPI 很适合做 API 服务，但不适合直接执行长时间 OCR 流程。

例如用户上传一个 PDF：

```text
POST /api/tasks/upload
```

如果 FastAPI 直接开始 OCR：

```text
上传请求
  ↓
FastAPI 渲染 PDF
  ↓
FastAPI 跑版面分析
  ↓
FastAPI 跑 OCR
  ↓
FastAPI 清洗文本
  ↓
FastAPI 导出 EPUB
  ↓
几分钟后才返回
```

这会让 HTTP 请求一直挂着。用户刷新页面、网络断开、浏览器超时，任务状态都会变得难处理。

更合理的方式是：

```text
上传请求
  ↓
FastAPI 保存文件
  ↓
FastAPI 创建任务记录
  ↓
FastAPI 把任务投递给 Celery
  ↓
FastAPI 立即返回 task_id
  ↓
Celery Worker 后台慢慢处理
  ↓
前端通过 task_id 查询进度
```

这样 FastAPI 只负责“接单”，Celery Worker 负责“干活”。

## 3. Celery、Worker、Redis 分别负责什么

这三个概念容易混在一起。

### 3.1 Celery

Celery 是 Python 的异步任务框架。

它负责定义：

- 什么是任务。
- 如何把任务投递到队列。
- Worker 如何从队列取任务。
- 任务成功或失败如何记录。

在项目中，Celery 负责把 OCR 流程变成后台任务。

### 3.2 Worker

Worker 是实际执行任务的进程。

启动 Worker 后，它会一直监听任务队列：

```text
等待任务
  ↓
拿到任务
  ↓
执行任务
  ↓
写入结果
  ↓
继续等待下一个任务
```

在本项目中，Worker 会执行：

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

### 3.3 Redis

Redis 在这里主要充当消息队列。

FastAPI 把任务放进 Redis：

```text
任务：处理 task_id=abc123
```

Worker 从 Redis 里取出这个任务并执行。

Redis 不负责 OCR，也不负责保存最终文件。它只是任务传递中间层。

## 4. 三者关系图

```text
用户
  ↓ 上传文件
React 前端
  ↓ POST /api/tasks/upload
FastAPI
  ↓ 写入任务记录
MySQL
  ↑
FastAPI
  ↓ 投递任务
Redis
  ↓ 分发任务
Celery Worker
  ↓ 执行 OCR 流程
backend/storage/tasks/{task_id}/
  ↓ 写入处理结果
MySQL 更新状态
  ↑
FastAPI 查询状态
  ↑
React 前端展示进度
```

## 5. 在 Mag2Read 项目中的作用

Mag2Read 的核心流程是：

```text
PDF / 图片上传
  ↓
页面渲染
  ↓
版面分析
  ↓
OCR
  ↓
文本清洗
  ↓
文档结构构建
  ↓
导出 EPUB / Markdown
```

这些步骤都适合放到 Worker 中执行。

FastAPI 只负责：

- 接收上传。
- 创建任务。
- 查询任务状态。
- 返回页面预览数据。
- 返回下载文件。

Celery Worker 负责：

- 调用 `backend/app/modules/render.py`
- 调用 `backend/app/modules/layout_detect.py`
- 调用 `backend/app/modules/layout_refine.py`
- 调用 `backend/app/modules/ocr.py`
- 调用 `backend/app/modules/text_cleaning.py`
- 调用 `backend/app/modules/document_build.py`
- 调用 `backend/app/modules/export_document.py`

## 6. 为什么本项目必须有 Worker

本项目和普通 CRUD 系统不同。

普通 CRUD 系统：

```text
查数据库
写数据库
返回 JSON
```

Mag2Read：

```text
处理大文件
加载深度学习模型
执行 OCR
写入大量中间文件
生成电子书
```

这些任务有几个特点：

- 执行时间长。
- 消耗 CPU / 内存。
- 可能失败。
- 需要记录阶段进度。
- 需要支持重试。
- 不适合阻塞 Web 请求。

Celery Worker 正好解决这些问题。

## 7. 和数据库的关系

Celery Worker 不直接替代数据库。

MySQL 仍然是任务状态的最终来源。

例如一个任务处理时，数据库状态可以这样变化：

```text
tasks.status = pending
  ↓
tasks.status = processing
tasks.current_stage = render
  ↓
task_steps.render = success
tasks.current_stage = layout_detect
  ↓
task_steps.layout_detect = success
tasks.current_stage = ocr
  ↓
task_steps.ocr = success
  ↓
tasks.status = success
```

Worker 每完成一步，就更新数据库：

- `tasks`
- `task_steps`
- `task_pages`
- `task_files`
- `export_records`

前端不直接问 Worker，而是通过 FastAPI 查数据库。

## 8. 和文件系统的关系

Worker 负责把处理结果写入任务目录：

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

例如：

```text
render.py
  ↓
pages/page_001.png

layout_detect.py
  ↓
layout_raw/page_001.json

ocr.py
  ↓
ocr/page_001.json

text_cleaning.py
  ↓
clean/document.json

export_document.py
  ↓
output/demo.epub
```

数据库只保存这些文件的路径和状态。

## 9. 项目中的最小 Celery 结构

当前阶段 0 中已经预留了基础结构：

```text
backend/app/workers/
  __init__.py
  celery_app.py
  tasks.py
```

其中：

- `celery_app.py`：创建 Celery 应用，配置 Redis。
- `tasks.py`：放具体后台任务。

最小任务示例：

```python
@celery_app.task(name="stage0.ping")
def ping() -> str:
    return "pong"
```

这个任务不处理 OCR，只用于验证 Worker 能不能启动、Redis 能不能传递任务。

## 10. 后续真正的 OCR 任务应该长什么样

后续可以设计一个任务：

```python
@celery_app.task(name="pipeline.process_task")
def process_task(task_id: str) -> dict:
    ...
```

它的大致逻辑是：

```text
读取 task_id
  ↓
更新 tasks.status = processing
  ↓
执行 render
  ↓
更新 task_steps.render
  ↓
执行 layout_detect
  ↓
更新 task_steps.layout_detect
  ↓
执行 layout_refine
  ↓
更新 task_steps.layout_refine
  ↓
执行 ocr
  ↓
更新 task_steps.ocr
  ↓
执行 text_cleaning
  ↓
更新 task_steps.text_cleaning
  ↓
执行 document_build
  ↓
执行 export
  ↓
更新 tasks.status = success
```

如果中间失败：

```text
捕获异常
  ↓
写入 task_steps.error_message
  ↓
写入 tasks.error_message
  ↓
tasks.status = failed
```

## 11. 如何启动 Celery Worker

在项目根目录执行：

```bash
celery -A backend.app.workers.celery_app.celery_app worker --loglevel=info
```

如果使用 conda：

```bash
conda run -n industrial-cv celery -A backend.app.workers.celery_app.celery_app worker --loglevel=info
```

含义：

```text
celery
  启动 Celery 命令行工具

-A backend.app.workers.celery_app.celery_app
  指定 Celery 应用对象

worker
  以 Worker 模式运行

--loglevel=info
  输出常规运行日志
```

## 12. 如何发送一个测试任务

保持 Redis 和 Worker 正在运行。

新开终端执行：

```bash
python -c "from backend.app.workers.tasks import ping; r = ping.delay(); print(r.get(timeout=10))"
```

如果输出：

```text
pong
```

说明：

- FastAPI 项目代码可导入。
- Celery 应用可用。
- Redis 队列可用。
- Worker 能收到任务。
- Worker 能返回结果。

## 13. 常见误区

### 13.1 Worker 不是 Web 服务

Worker 不对浏览器提供接口。

浏览器访问的是 FastAPI：

```text
http://127.0.0.1:8000
```

Worker 在后台运行，不需要浏览器访问。

### 13.2 Redis 不保存最终结果

Redis 在本项目中主要是任务队列和临时结果后端。

最终任务状态仍然保存到 MySQL。

最终文件仍然保存到：

```text
backend/storage/tasks/{task_id}/
```

### 13.3 Celery 不等于多线程

Celery 更像“多进程后台任务系统”。

它可以启动多个 Worker，也可以让一个 Worker 同时处理多个任务。

但是对 PaddleOCR 这种模型任务，要控制并发数量，避免内存爆掉。

### 13.4 不是所有接口都要进 Celery

这些接口不需要 Celery：

- 查询任务列表。
- 查询任务详情。
- 下载文件。
- 获取页面图片。
- 获取 OCR JSON。

这些任务适合 Celery：

- PDF 渲染。
- OCR。
- 版面分析。
- 大模型导读。
- EPUB / DOCX 导出。

## 14. 本项目推荐的 Worker 策略

第一阶段建议：

```text
FastAPI 进程：1 个
Celery Worker：1 个
Worker 并发数：1
Redis：1 个
MySQL：1 个
```

原因：

- PaddleOCR 模型比较占内存。
- 课程项目演示不需要高并发。
- 单 Worker 更容易排查问题。

启动 Worker 时可以限制并发：

```bash
celery -A backend.app.workers.celery_app.celery_app worker --loglevel=info --concurrency=1
```

后续如果要支持多个用户并发，可以增加 Worker 数量或拆队列：

```text
queue: render
queue: ocr
queue: export
queue: ai
```

但第一版不建议过早拆复杂。

## 15. 在答辩中怎么解释

可以这样说：

```text
本系统的 OCR、版面分析和电子书导出都属于耗时任务。
如果直接放在 Web 请求中执行，会导致接口阻塞和用户长时间等待。
因此系统采用 FastAPI + Redis + Celery Worker 的异步任务架构。
FastAPI 负责接收上传和查询状态，Celery Worker 在后台执行 OCR 流程，
MySQL 保存任务进度，前端通过 task_id 查询每一步处理状态。
```

这能体现系统不是简单脚本，而是具备完整工程架构的 Web 应用。

## 16. 一句话总结

Celery Worker 是 Mag2Read 的后台处理工人。

FastAPI 负责接收任务，Redis 负责传递任务，Worker 负责执行耗时 OCR 流程，MySQL 负责记录任务状态，前端负责展示进度和结果。
