# 阶段 3.5 OCR 监控增强手动测试文档

## 1. 测试目标

本阶段只做 OCR 监控增强，不改变 OCR 算法。

目标是定位 OCR 阶段慢在哪里：

- PaddleOCR 模型初始化慢。
- 单页 OCR 慢。
- block 数太多。
- 单个 block 的 `predict` 慢。
- 模型缓存没有命中，导致加载或下载异常。

监控结果会写入：

```text
backend/storage/tasks/{task_id}/ocr/summary.json
backend/storage/tasks/{task_id}/ocr/page_*.json
task_steps.summary_json
Celery Worker 控制台日志
```

## 2. 新增监控字段

### 2.1 任务级 OCR 监控

位置：

```text
backend/storage/tasks/{task_id}/ocr/summary.json
```

重点字段：

```json
{
  "timing": {
    "ocr_model_init_seconds": 12.3,
    "total_ocr_seconds": 45.6,
    "total_page_ocr_seconds": 33.3,
    "total_block_seconds": 31.8,
    "total_predict_seconds": 28.4,
    "avg_page_ocr_seconds": 33.3,
    "avg_block_seconds": 1.2,
    "avg_predict_seconds": 1.0,
    "max_page_ocr_seconds": 33.3,
    "max_block_seconds": 4.8,
    "max_predict_seconds": 4.3,
    "slow_block_count": 2,
    "slow_blocks": [],
    "paddlex_cache_dir": "backend/storage/paddlex_cache",
    "models_added": []
  }
}
```

字段含义：

| 字段 | 含义 |
| --- | --- |
| `ocr_model_init_seconds` | PaddleOCR 初始化耗时 |
| `total_page_ocr_seconds` | 所有页面 OCR 总耗时，不含模型初始化 |
| `total_predict_seconds` | 所有 block 的 `ocr.predict()` 总耗时 |
| `avg_block_seconds` | 平均每个 block 耗时 |
| `max_block_seconds` | 最慢 block 总耗时 |
| `slow_block_count` | 慢 block 数量，默认阈值 2 秒 |
| `models_added` | OCR 初始化期间新增的模型目录，用于判断是否发生模型下载 |

### 2.2 页面级 OCR 监控

位置：

```text
backend/storage/tasks/{task_id}/ocr/page_001.json
```

重点字段：

```json
{
  "timing": {
    "page_ocr_seconds": 33.3,
    "total_block_seconds": 31.8,
    "total_predict_seconds": 28.4,
    "avg_block_seconds": 1.2,
    "max_block_seconds": 4.8,
    "slow_block_count": 2,
    "slow_blocks": []
  }
}
```

### 2.3 block 级 OCR 监控

位置：

```text
backend/storage/tasks/{task_id}/ocr/page_001.json
```

每个 `blocks[]` 中新增：

```json
{
  "block_id": "p001_b0001",
  "timing": {
    "crop_seconds": 0.001,
    "crop_save_seconds": 0.003,
    "predict_seconds": 1.25,
    "cleanup_seconds": 0.0,
    "total_seconds": 1.26,
    "is_slow": false
  }
}
```

如果 `predict_seconds` 很高，说明慢在 PaddleOCR 推理。  
如果 `crop_save_seconds` 很高，说明慢在大量临时图片读写。  
如果 `ocr_model_init_seconds` 很高，说明慢在模型初始化。

## 3. 前置条件

进入项目目录：

```bash
cd /Users/zhu/projects/python-project/课程项目2
```

确认 Redis、MySQL、FastAPI、Celery Worker 都能启动。

建议 Worker 用单并发：

```bash
conda run -n industrial-cv celery -A backend.app.workers.celery_app.celery_app worker --loglevel=info --concurrency=1
```

## 4. 上传单张图片测试

推荐先用单张图片，不要直接用多页 PDF。

```bash
curl -X POST http://127.0.0.1:8000/api/tasks/upload \
  -F "file=@pdfs/poet.jpg" \
  -F "task_id=manual_ocr_monitor_poet" \
  -F "output_format=markdown,epub" \
  -F "auto_start=true"
```

观察 Celery Worker 日志。

预期会看到类似：

```text
[ocr] initializing PaddleOCR, cache_dir=...
[ocr] PaddleOCR initialized in 12.3456s
[ocr] page 1 started: page_001.json
[ocr] page 1 finished: blocks=8, recognized=8, page_seconds=10.2, predict_seconds=9.6, slow_blocks=1
[ocr] task finished: total=22.5s, init=12.3s, page_total=10.2s, predict_total=9.6s, slow_blocks=1
```

## 5. 查询任务状态

```bash
curl http://127.0.0.1:8000/api/tasks/manual_ocr_monitor_poet
```

成功时：

```json
{
  "status": "success",
  "progress": 100
}
```

失败时：

```json
{
  "status": "failed",
  "current_stage": "ocr",
  "error_message": "..."
}
```

## 6. 查询 OCR 阶段 summary_json

```bash
curl http://127.0.0.1:8000/api/tasks/manual_ocr_monitor_poet/steps
```

找到：

```json
{
  "stage": "ocr",
  "summary_json": {
    "ocr_block_count": 8,
    "recognized_block_count": 8,
    "timing": {
      "ocr_model_init_seconds": 12.3,
      "total_ocr_seconds": 22.5,
      "total_predict_seconds": 9.6,
      "slow_block_count": 1
    }
  }
}
```

如果这里能看到 `timing`，说明数据库监控写入成功。

## 7. 查看 OCR summary 文件

```bash
python -m json.tool backend/storage/tasks/manual_ocr_monitor_poet/ocr/summary.json | less
```

重点看：

```text
timing.ocr_model_init_seconds
timing.total_page_ocr_seconds
timing.total_predict_seconds
timing.slow_block_count
timing.slow_blocks
pages[].timing
```

## 8. 查看页面 OCR 文件

```bash
python -m json.tool backend/storage/tasks/manual_ocr_monitor_poet/ocr/page_001.json | less
```

重点看：

```text
timing
blocks[].timing
```

如果某个 block 很慢，可以记录：

```text
block_id
role
crop_width
crop_height
predict_seconds
total_seconds
text_length
```

## 9. 如何判断慢在哪里

### 9.1 模型初始化慢

表现：

```text
ocr_model_init_seconds 很高
total_predict_seconds 不高
```

可能原因：

- 首次加载 PaddleOCR 模型。
- 模型缓存路径不对。
- 模型目录不存在，触发下载或检查。
- Worker 每个任务重新初始化 OCR。

后续优化：

- Worker 启动时预加载 OCR。
- 复用 OCR 实例。
- 确认 `backend/storage/paddlex_cache` 有模型。

### 9.2 分块 OCR 太慢

表现：

```text
ocr_block_count 很高
total_predict_seconds 很高
avg_predict_seconds 正常
```

说明：

单次 predict 不算慢，但 block 太多，调用次数堆起来很慢。

后续优化：

- 合并相邻正文 block。
- 改成整页 OCR 后按 bbox 归属。
- 对明显非正文 block 跳过 OCR。

### 9.3 单个 block 异常慢

表现：

```text
slow_block_count > 0
slow_blocks 中某些 block predict_seconds 很高
```

可能原因：

- crop 区域太大。
- block 是复杂图文区域。
- layout 把整页或大图误识别为正文。

后续优化：

- 对超大 bbox 加规则跳过。
- 对低置信 layout block 降级处理。
- 对复杂页走 VLM 或整页 OCR。

### 9.4 临时图片读写慢

表现：

```text
crop_save_seconds 总和明显偏高
predict_seconds 不高
```

后续优化：

- 避免每个 block 落盘，改成内存图像输入。
- 或集中保存 crop，仅调试模式保存。

## 10. MySQL 直接检查

进入 MySQL：

```bash
mysql -u root -p
```

执行：

```sql
USE mag2read;

SELECT stage, status, duration_ms, summary_json
FROM task_steps
WHERE task_id = 'manual_ocr_monitor_poet'
  AND stage = 'ocr';
```

预期：

```text
summary_json 中包含 timing
duration_ms 接近 total_ocr_seconds * 1000
```

## 11. 清理测试数据

```sql
USE mag2read;
DELETE FROM tasks WHERE task_id = 'manual_ocr_monitor_poet';
```

```bash
rm -rf backend/storage/tasks/manual_ocr_monitor_poet
```

## 12. 本阶段验收清单

- [ ] Celery Worker 日志能打印 OCR 初始化耗时。
- [ ] Celery Worker 日志能打印每页 OCR 耗时。
- [ ] `ocr/summary.json` 中有 `timing`。
- [ ] `ocr/page_001.json` 中有页面级 `timing`。
- [ ] `ocr/page_001.json` 的 `blocks[]` 中有 block 级 `timing`。
- [ ] `GET /api/tasks/{task_id}/steps` 的 OCR 阶段 `summary_json` 中有 timing。
- [ ] 能根据 timing 判断慢在模型初始化、predict 调用次数，还是慢 block。

## 13. 下一步判断

完成本阶段测试后，根据结果选择优化方向：

| 现象 | 下一步 |
| --- | --- |
| `ocr_model_init_seconds` 占比最大 | 做 Worker OCR 模型预加载和复用 |
| `ocr_block_count` 很高 | 做 block 合并或整页 OCR |
| `slow_blocks` 集中在大 bbox | 加超大 block 跳过或降级规则 |
| `crop_save_seconds` 很高 | 改成内存 crop，减少磁盘 IO |
