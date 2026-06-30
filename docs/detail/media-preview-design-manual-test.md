# 阅读预览媒体展示设计与手动测试说明

## 1. 问题背景

阅读预览区域希望可以选择性展示图片、表格、公式等非纯文字内容。之前的实现方式是：

```text
clean/document.json 中的 block.bbox
  ↓
前端拼接 /api/tasks/{task_id}/pages/{page_no}/crop?x1=...
  ↓
后端从页面 PNG 中即时裁剪
```

这个方案在本地模式下有时可用，但在云端模式下容易裁错。主要原因是坐标系不一致：

```text
百度返回 bbox 可能基于 PDF 页面坐标，如 612 x 792
本地渲染页面 PNG 可能是像素坐标，如 1700 x 2200
```

如果前端把百度坐标直接传给后端裁剪本地 PNG，就会裁到错误区域，导致图片不是原文中的图片部分。

## 2. 设计目标

本次采用“预生成媒体文件”的方案：

```text
layout/ocr 结果
  ↓
media_builder 统一裁剪图像、表格、公式区域
  ↓
media/*.png 落盘
  ↓
clean/document.json 写入 media_path
  ↓
前端阅读预览按 media_path 展示
```

目标是：

- 前端不再自己计算裁剪参数。
- 本地 Paddle 和百度云端都走同一套媒体生成逻辑。
- 坐标缩放由后端集中处理。
- 阅读预览、后续 DOCX/EPUB 插图都可以复用 `media` 文件。

## 3. 新增模块

新增文件：

```text
backend/app/modules/media_builder.py
```

核心职责：

1. 读取 `layout/page_*.json`。
2. 找出 `figure`、`image`、`table`、`formula` 这类图形块。
3. 找到对应页面图片：

```text
backend/storage/tasks/{task_id}/pages/page_001.png
```

4. 根据 layout 坐标和页面 PNG 像素尺寸计算缩放比例。
5. 裁剪真实页面区域，保存到：

```text
backend/storage/tasks/{task_id}/media/
```

6. 写入：

```text
backend/storage/tasks/{task_id}/media/summary.json
```

## 4. 数据结构

### 4.1 media/summary.json

示例：

```json
{
  "task_id": "demo_task",
  "stage": "media",
  "media_count": 3,
  "items": [
    {
      "block_id": "p001_b0005",
      "page_no": 1,
      "role": "figure",
      "media_path": "backend/storage/tasks/demo_task/media/page_001_p001_b0005_figure.png",
      "source_image_path": "backend/storage/tasks/demo_task/pages/page_001.png",
      "bbox": {
        "x1": 120,
        "y1": 280,
        "x2": 520,
        "y2": 480
      },
      "crop_box": {
        "x1": 333,
        "y1": 778,
        "x2": 1444,
        "y2": 1333
      },
      "width": 1111,
      "height": 555
    }
  ]
}
```

这里的 `bbox` 是识别模型返回或修正后的版面坐标；`crop_box` 是实际页面 PNG 上的像素坐标。

### 4.2 clean/document.json

清洗阶段会读取 `media/summary.json`，并把媒体路径写回清洗文档：

```json
{
  "id": "c00012",
  "type": "figure",
  "role": "figure",
  "text": "",
  "source_pages": [1],
  "source_block_ids": ["p001_b0005"],
  "is_graphical": true,
  "bbox": {
    "x1": 120,
    "y1": 280,
    "x2": 520,
    "y2": 480
  },
  "media_path": "backend/storage/tasks/demo_task/media/page_001_p001_b0005_figure.png",
  "media_width": 1111,
  "media_height": 555
}
```

前端只需要读取 `media_path`，不再使用 bbox 裁剪。

## 5. 流水线位置

Celery 中的位置如下：

```text
render
  ↓
本地识别或百度云端识别
  ↓
media_builder
  ↓
text_cleaning
  ↓
document_build
  ↓
export
```

这样安排的原因：

- `render` 后有页面 PNG。
- 识别后有 `layout/page_*.json` 和图形块 bbox。
- `text_cleaning` 前生成 media，清洗文档才能写入 `media_path`。

## 6. 后端接口

新增接口：

```text
GET /api/tasks/{task_id}/media/{filename}
```

用途：

- 从任务目录的 `media` 文件夹读取 PNG。
- 只允许读取当前任务下的 PNG 文件。
- 前端阅读预览使用这个接口展示图片、表格、公式区域。

旧接口仍保留：

```text
GET /api/tasks/{task_id}/pages/{page_no}/crop
```

旧接口主要用于调试，不再作为阅读预览的主路径。

## 7. 前端展示逻辑

阅读预览区域仍保留“图片”开关。

关闭时：

```text
只展示正文、标题、普通段落
```

开启时：

```text
展示 figure / image / table / formula 等 is_graphical 块
```

前端展示流程：

```text
clean/document.json
  ↓
找到 is_graphical=true 的 block
  ↓
读取 block.media_path
  ↓
提取文件名
  ↓
请求 /api/tasks/{task_id}/media/{filename}
```

如果旧任务没有 `media_path`，界面会显示“媒体素材未生成”，而不是错误裁剪。

## 8. 手动测试步骤

### 8.1 测试本地模式

1. 启动后端、Redis、Celery worker 和前端。
2. 打开前端首页。
3. 上传一张包含图片或表格的文件。
4. 高级选项选择“本地识别”。
5. 等任务完成。
6. 打开任务详情页。
7. 在“阅读稿预览”中打开“图片”开关。
8. 检查图片或表格区域是否是原文中的对应区域。

重点检查：

```text
backend/storage/tasks/{task_id}/media/
backend/storage/tasks/{task_id}/media/summary.json
backend/storage/tasks/{task_id}/clean/document.json
```

`clean/document.json` 中对应媒体块应包含：

```text
is_graphical: true
media_path: ...
media_width: ...
media_height: ...
```

### 8.2 测试百度云端模式

1. 确认 `.env` 中有百度凭证：

```bash
BAIDU_OCR_API_KEY=...
BAIDU_OCR_SECRET_KEY=...
```

2. 上传多页 PDF。
3. 高级选项选择“云端增强”。
4. 等待任务完成。
5. 打开任务详情页。
6. 打开阅读预览里的“图片”开关。
7. 检查图片、表格、公式区域是否对应原文。

重点检查：

```text
backend/storage/tasks/{task_id}/cloud/baidu_parse_result.json
backend/storage/tasks/{task_id}/layout/page_001.json
backend/storage/tasks/{task_id}/media/summary.json
backend/storage/tasks/{task_id}/clean/document.json
```

如果百度坐标和本地 PNG 坐标不同，`media/summary.json` 中的 `crop_box` 应该已经是缩放后的像素坐标。

### 8.3 只用已有任务补生成 media

如果已有任务已经有 `layout` 和 `pages`，但还没有 `media`，可以手动运行：

```bash
conda run -n industrial-cv python -c "from pathlib import Path; from backend.app.modules.media_builder import build_media_assets; build_media_assets(Path('backend/storage/tasks/{task_id}'))"
```

然后重新运行清洗：

```bash
conda run -n industrial-cv python backend/app/modules/text_cleaning.py backend/storage/tasks/{task_id}
```

再刷新前端任务详情页。

## 9. 排查方法

### 9.1 前端显示“媒体素材未生成”

检查：

```text
media/summary.json 是否存在
clean/document.json 中是否有 media_path
media_path 对应的 PNG 是否存在
```

如果没有 `media/summary.json`，说明媒体生成阶段没有执行或没有识别到图形块。

### 9.2 图片仍然裁错

检查 `media/summary.json`：

```text
bbox      模型坐标
crop_box  实际 PNG 像素坐标
```

再查看 `layout/page_*.json` 中的：

```text
width
height
bbox
```

如果 `width/height` 为 0 或明显不对，会导致缩放比例错误。此时需要修正 layout 元数据来源。

### 9.3 没有图片块

检查 `layout/page_*.json` 中是否存在：

```text
role: figure
role: image
role: table
role: formula
```

如果版面识别没有识别出这些 role，media_builder 不会生成媒体文件。

## 10. 当前限制

- 媒体文件目前只生成 PNG。
- 旧任务需要重新运行 media_builder 和 text_cleaning 才能显示媒体。
- DOCX/EPUB 导出暂未把 `media_path` 插入最终文件，本次主要解决阅读预览。
- 如果版面模型把图片区域识别错，media_builder 会忠实裁剪错误区域；这类问题需要优化版面识别或人工修正 bbox。

## 11. 后续可扩展方向

- DOCX 导出插入 `media_path` 图片。
- EPUB 导出把媒体文件加入书籍资源。
- 前端给媒体块增加“查看原页位置”按钮。
- 为媒体块增加类型筛选：图片、表格、公式分别开关。
- 对百度返回的 `images[].data_url` 做优先下载，下载失败时再回退到页面裁剪。
