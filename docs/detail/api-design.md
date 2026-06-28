# 接口设计文档

## 1. 接口约定

后端基础路径：

```text
/api
```

响应格式建议：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

错误响应：

```json
{
  "code": 40001,
  "message": "只支持 PDF 文件",
  "data": null
}
```

## 2. 创建转换任务

```text
POST /api/tasks
```

请求类型：`multipart/form-data`

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| file | file | 是 | PDF 文件 |
| target_format | string | 是 | docx、epub、html、md、txt |
| ocr_language | string | 否 | ch、en，默认 ch |
| enable_layout | boolean | 否 | 是否启用版面分析 |
| enhance_image | boolean | 否 | 是否启用图像增强 |

响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "task_20260624_001"
  }
}
```

## 3. 查询任务详情

```text
GET /api/tasks/{task_id}
```

响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "task_20260624_001",
    "original_filename": "scan.pdf",
    "target_format": "docx",
    "source_type": "scanned_pdf",
    "status": "processing",
    "progress": 65,
    "ocr_avg_confidence": 0.93,
    "created_at": "2026-06-24T10:00:00",
    "updated_at": "2026-06-24T10:01:30",
    "error_message": null
  }
}
```

## 4. 查询任务列表

```text
GET /api/tasks
```

查询参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| page | integer | 页码 |
| page_size | integer | 每页数量 |
| status | string | 可选任务状态 |

响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 1,
    "items": [
      {
        "id": "task_20260624_001",
        "original_filename": "scan.pdf",
        "target_format": "docx",
        "status": "success",
        "progress": 100,
        "created_at": "2026-06-24T10:00:00"
      }
    ]
  }
}
```

## 5. 下载转换结果

```text
GET /api/tasks/{task_id}/download
```

说明：

- 任务成功后才允许下载。
- 后端返回文件流。
- 文件名建议使用原始文件名加目标格式后缀。

## 6. 获取 HTML 预览

```text
GET /api/tasks/{task_id}/preview
```

响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "type": "html",
    "content": "<h1>标题</h1><p>正文内容</p>"
  }
}
```

## 7. 查询 OCR 质量报告

```text
GET /api/tasks/{task_id}/quality
```

响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "page_count": 12,
    "ocr_avg_confidence": 0.94,
    "low_confidence_count": 18,
    "text_block_count": 260,
    "image_block_count": 14,
    "table_block_count": 3,
    "processing_seconds": 42.6
  }
}
```

## 8. 前端轮询逻辑

前端创建任务后跳转到任务详情页：

```text
/tasks/{task_id}
```

轮询规则：

- 任务状态为 `pending` 或 `processing` 时，每 1 到 2 秒请求一次详情。
- 状态为 `success` 时显示下载和预览。
- 状态为 `failed` 时显示失败原因。

