# 第一层版面分析手动验证文档

## 1. 验证目标

验证第一层版面分析是否能读取标准页面图，并输出 PP-DocLayout / PaddleOCR LayoutDetection 的原始版面检测结果。

第一层只负责“看见页面上有什么”，不负责最终阅读顺序和规则修正。

输出内容：

- `layout_raw/page_xxx.json`：每页原始版面检测结果。
- `layout_raw/summary.json`：任务级检测汇总。
- `debug/page_xxx_layout_overlay.png`：带检测框的调试图。

## 2. 运行环境

本项目 Python 脚本使用 Conda 环境：

```bash
conda run -n industrial-cv python ...
```

不要直接使用系统默认 `python`，否则可能进入 `base` 环境并缺少 PyMuPDF、PaddleOCR 等依赖。

脚本会默认把 PaddleX 模型缓存写入：

```text
backend/storage/paddlex_cache
```

这样可以避开 Conda 环境中错误的 `PADDLE_PDX_CACHE_HOME`。

## 3. 测试前准备

进入项目根目录：

```bash
cd /Users/zhu/projects/python-project/课程项目2
```

确认脚本语法：

```bash
conda run -n industrial-cv python -m py_compile backend/scripts/analyze_layout.py
```

预期：无输出，退出码为 0。

## 4. 验证一：单张复杂截图

### 4.1 先生成标准页面图

```bash
conda run -n industrial-cv python backend/scripts/render_pdf_pages.py pdfs/complexLayout.jpg --task-id manual_layout_complex --overwrite
```

预期：

```text
Rendered 1 page(s).
Task ID: manual_layout_complex
```

### 4.2 执行版面分析

```bash
conda run -n industrial-cv python backend/scripts/analyze_layout.py manual_layout_complex
```

预期：

```text
Analyzed 1 page(s).
Task ID: manual_layout_complex
Raw blocks: ...
Summary: backend/storage/tasks/manual_layout_complex/layout_raw/summary.json
```

### 4.3 检查输出文件

```bash
find backend/storage/tasks/manual_layout_complex -maxdepth 3 -type f | sort
```

应包含：

```text
backend/storage/tasks/manual_layout_complex/layout_raw/page_001.json
backend/storage/tasks/manual_layout_complex/layout_raw/summary.json
backend/storage/tasks/manual_layout_complex/debug/page_001_layout_overlay.png
```

### 4.4 检查 JSON

```bash
sed -n '1,220p' backend/storage/tasks/manual_layout_complex/layout_raw/page_001.json
```

重点检查：

- `task_id` 正确。
- `page_no` 为 `1`。
- `image_path` 指向 `pages/page_001.png`。
- `width`、`height` 不为空。
- `detector.name` 为 `PaddleOCR LayoutDetection`。
- `raw_blocks` 非空。
- 每个 `raw_blocks[]` 包含：
  - `raw_id`
  - `raw_type`
  - `cls_id`
  - `score`
  - `bbox.x1/y1/x2/y2`

### 4.5 检查 overlay

```bash
file backend/storage/tasks/manual_layout_complex/debug/page_001_layout_overlay.png
```

预期：

```text
PNG image data, ... RGB ...
```

人工打开图片检查：

- 检测框没有整体错位。
- 主要图片区域能被框出。
- 主要正文区域能被框出。
- 页眉/页脚或顶部状态栏可能被识别为 `header`，这是第一层允许的结果，第二层规则会继续修正。

## 5. 验证二：图片目录多页检测

### 5.1 生成页面图

```bash
conda run -n industrial-cv python backend/scripts/render_pdf_pages.py pdfs --task-id manual_layout_images --overwrite
```

### 5.2 执行版面分析

```bash
conda run -n industrial-cv python backend/scripts/analyze_layout.py manual_layout_images
```

### 5.3 检查汇总

```bash
sed -n '1,260p' backend/storage/tasks/manual_layout_images/layout_raw/summary.json
```

当前 `pdfs/` 目录图片样例的参考结果：

```text
page_001 complexLayout.jpg -> text/image/paragraph_title/header/footer
page_002 handwrite.jpg     -> 可能大量识别为 formula
page_003 poet.jpg          -> text/image
page_004 table.jpg         -> table/image/text/doc_title
```

注意：手写笔记被识别成 `formula` 是模型原始输出，不代表最终分类。第二层规则或 OCR 阶段会继续处理。

## 6. 验证三：PDF 多页检测

### 6.1 生成页面图

```bash
conda run -n industrial-cv python backend/scripts/render_pdf_pages.py pdfs/pdf1.0.pdf --task-id manual_layout_pdf --overwrite
```

### 6.2 执行版面分析

```bash
conda run -n industrial-cv python backend/scripts/analyze_layout.py manual_layout_pdf
```

### 6.3 检查输出

```bash
find backend/storage/tasks/manual_layout_pdf/layout_raw -maxdepth 1 -type f | sort
find backend/storage/tasks/manual_layout_pdf/debug -maxdepth 1 -type f | sort
```

预期：

- 每个 `page_xxx.png` 都有一个 `layout_raw/page_xxx.json`。
- 每个页面都有一个 `debug/page_xxx_layout_overlay.png`。
- `layout_raw/summary.json` 中 `page_count` 等于渲染页数。
- `total_raw_blocks` 大于 0。

## 7. 可选参数

### 7.1 指定检测阈值

```bash
conda run -n industrial-cv python backend/scripts/analyze_layout.py manual_layout_complex --threshold 0.6
```

阈值越高，保留的低置信度框越少。第一阶段建议先不设置，让模型输出尽量完整，再交给第二层规则过滤。

### 7.2 不生成 overlay 图

```bash
conda run -n industrial-cv python backend/scripts/analyze_layout.py manual_layout_complex --no-debug-overlay
```

用于批量处理时减少图片输出。

## 8. 通过标准

满足以下条件即可认为第一层版面分析通过：

- `analyze_layout.py` 能在 `industrial-cv` 环境中运行。
- 能读取 `backend/storage/tasks/{task_id}/pages/page_xxx.png`。
- 每页能生成 `layout_raw/page_xxx.json`。
- 能生成 `layout_raw/summary.json`。
- 默认能生成 overlay 调试图。
- `raw_blocks` 中包含模型原始类型、置信度和坐标。
- 图片目录和 PDF 多页任务都能批量处理。

## 9. 当前已验证结果

当前已跑通的任务：

```text
layout_probe_complex -> 1 页，31 个 raw blocks
layout_step1_images  -> 4 页，59 个 raw blocks
layout_step1_pdf     -> 6 页，64 个 raw blocks
```

其中 `layout_step1_images` 的标签分布显示：

```text
complexLayout: text/image/paragraph_title/header/footer
handwrite: formula/text
poet: text/image
table: table/image/text/doc_title
```

这说明第一层已经能对不同类型页面给出可用的原始版面候选框。

## 10. 下一步

第一层完成后，下一步实现第二层规则修正：

- 把 `raw_type` 映射为内部 `role`。
- 统一输出 `layout/page_xxx.json`。
- 判断单栏、双栏、多栏、复杂混排。
- 标记 `reading_group`。
- 生成初步阅读顺序 `order`。
- 计算 `complexity.need_vlm`。
