# 系统架构设计

## 1. 总体架构

系统采用前后端分离架构：

- 前端：React + TypeScript + Vite
- 后端：FastAPI
- 异步任务：Celery 或 RQ
- 消息队列：Redis
- 数据库：SQLite 起步，后期可替换为 PostgreSQL
- OCR 引擎：PaddleOCR
- 文件存储：本地文件系统，后期可扩展为对象存储

整体流程：

```text
React 前端
  ↓
FastAPI 接口服务
  ↓
任务队列 Redis
  ↓
OCR Worker
  ↓
PDF 渲染 / 图片预处理 / OCR / 版面分析 / 格式导出
  ↓
结果文件存储
  ↓
前端预览与下载
```

## 2. 技术选型

### 2.1 前端

推荐：

- React
- TypeScript
- Vite
- Ant Design 或 Arco Design
- Axios
- React Router
- TanStack Query

选择理由：

- React 生态成熟，适合课程项目展示。
- TypeScript 能提升代码规范性。
- Ant Design 提供成熟的上传、表格、进度条、消息提示等组件。
- TanStack Query 适合轮询任务状态。

### 2.2 后端

推荐：

- FastAPI
- SQLAlchemy
- Pydantic
- Celery 或 RQ
- Redis

选择理由：

- FastAPI 接口开发效率高，自动生成 OpenAPI 文档。
- Pydantic 适合定义请求和响应模型。
- OCR 转换是耗时任务，必须异步处理。

### 2.3 PDF 与 OCR

推荐：

- PyMuPDF：PDF 页面渲染、图片提取、文本初步判断。
- PaddleOCR：中文 OCR 识别。
- OpenCV：图像预处理。
- python-docx：生成 Word 文档。
- ebooklib：生成 EPUB。
- Jinja2：生成 HTML 模板。

## 3. 后端模块划分

建议目录：

```text
backend/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── files.py
│   │   ├── tasks.py
│   │   └── downloads.py
│   ├── core/
│   │   ├── config.py
│   │   └── storage.py
│   ├── db/
│   │   ├── session.py
│   │   └── models.py
│   ├── schemas/
│   │   └── task.py
│   ├── services/
│   │   ├── pdf_classifier.py
│   │   ├── pdf_renderer.py
│   │   ├── image_preprocessor.py
│   │   ├── ocr_engine.py
│   │   ├── layout_analyzer.py
│   │   ├── document_builder.py
│   │   └── exporters/
│   │       ├── docx_exporter.py
│   │       ├── epub_exporter.py
│   │       ├── html_exporter.py
│   │       ├── markdown_exporter.py
│   │       └── txt_exporter.py
│   └── workers/
│       └── convert_tasks.py
├── storage/
│   ├── uploads/
│   ├── pages/
│   └── outputs/
└── requirements.txt
```

## 4. 前端模块划分

建议目录：

```text
frontend/
├── src/
│   ├── api/
│   │   ├── client.ts
│   │   └── tasks.ts
│   ├── components/
│   │   ├── FileUploader.tsx
│   │   ├── FormatSelector.tsx
│   │   ├── TaskProgress.tsx
│   │   └── ResultPreview.tsx
│   ├── pages/
│   │   ├── ConvertPage.tsx
│   │   ├── HistoryPage.tsx
│   │   └── TaskDetailPage.tsx
│   ├── routes/
│   │   └── index.tsx
│   ├── types/
│   │   └── task.ts
│   └── main.tsx
└── package.json
```

## 5. 数据库设计

### 5.1 转换任务表

表名：`conversion_tasks`

字段建议：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | 任务 ID |
| original_filename | string | 原始文件名 |
| stored_filename | string | 存储文件名 |
| file_size | integer | 文件大小 |
| source_type | string | PDF 类型 |
| target_format | string | 目标格式 |
| ocr_language | string | OCR 语言 |
| status | string | 任务状态 |
| progress | integer | 进度 |
| output_path | string | 输出文件路径 |
| error_message | text | 错误信息 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## 6. 中间文档模型

OCR 和导出之间应使用统一的中间结构：

```json
{
  "title": "文档标题",
  "source_type": "scanned_pdf",
  "pages": [
    {
      "page_no": 1,
      "width": 1240,
      "height": 1754,
      "blocks": [
        {
          "type": "heading",
          "text": "第一章 绪论",
          "bbox": [120, 80, 900, 140],
          "confidence": 0.98
        },
        {
          "type": "paragraph",
          "text": "正文内容……",
          "bbox": [120, 180, 900, 260],
          "confidence": 0.95
        }
      ]
    }
  ]
}
```

这样设计的好处是导出模块不直接依赖 OCR 引擎，后续更换 OCR 或新增格式都比较方便。

## 7. 任务执行流程

```text
1. 前端上传 PDF
2. 后端保存文件并创建任务
3. 后端把任务 ID 投递到 Redis 队列
4. Worker 获取任务
5. 判断 PDF 类型
6. 渲染页面为图片
7. 对图片进行预处理
8. 执行 OCR 识别
9. 进行版面分析和阅读顺序排序
10. 构建中间文档模型
11. 导出目标格式文件
12. 更新任务状态为 success 或 failed
13. 前端轮询任务状态并显示下载按钮
```

## 8. 部署方案

课程项目推荐使用 Docker Compose：

```text
docker-compose.yml
├── frontend
├── backend
├── worker
├── redis
└── database
```

初期开发阶段可以先本地启动：

- `uvicorn app.main:app --reload`
- `celery -A app.workers.convert_tasks worker --loglevel=info`
- `npm run dev`

