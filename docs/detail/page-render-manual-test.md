# 页面转换功能手动验证文档

## 1. 验证目标

本次验证页面转换模块是否能把不同输入统一转换为后续版面分析和 OCR 可直接使用的标准页面图。

当前支持输入：

- PDF 文件。
- 单张图片，例如 JPG、PNG。
- 图片目录，例如 `pdfs/` 下多张测试图片。

标准输出要求：

- 输出目录为 `backend/storage/tasks/{task_id}/pages/`。
- 页面文件命名为 `page_001.png`、`page_002.png` 等连续编号。
- 输出图片为 PNG 格式。
- 输出图片为 RGB，无透明通道。
- `metadata.json` 正确记录输入类型、源文件、页数、图片宽高和输出路径。
- `metadata.json` 包含图像质量检查结果，详细验证见 `docs/image-quality-manual-test.md`。

## 2. 测试前准备

在项目根目录执行：

```bash
cd /Users/zhu/projects/python-project/课程项目2
```

确认测试文件存在：

```bash
find pdfs -maxdepth 1 -type f
```

应至少能看到：

```text
pdfs/pdf1.0.pdf
pdfs/complexLayout.jpg
pdfs/handwrite.jpg
pdfs/poet.jpg
pdfs/table.jpg
```

## 3. 验证一：PDF 转页面图片

### 3.1 执行命令

```bash
python backend/scripts/render_pdf_pages.py pdfs/pdf1.0.pdf --task-id manual_pdf --overwrite
```

### 3.2 预期命令输出

应看到类似输出：

```text
Rendered 6 page(s).
Task ID: manual_pdf
Output: backend/storage/tasks/manual_pdf
Metadata: backend/storage/tasks/manual_pdf/metadata.json
```

页数以实际 PDF 为准。

### 3.3 检查输出文件

```bash
find backend/storage/tasks/manual_pdf -maxdepth 2 -type f
```

应包含：

```text
backend/storage/tasks/manual_pdf/input/original.pdf
backend/storage/tasks/manual_pdf/metadata.json
backend/storage/tasks/manual_pdf/pages/page_001.png
backend/storage/tasks/manual_pdf/pages/page_002.png
...
```

### 3.4 检查图片格式

```bash
file backend/storage/tasks/manual_pdf/pages/page_001.png
```

预期：

```text
PNG image data, ... RGB ...
```

### 3.5 检查 metadata

```bash
sed -n '1,220p' backend/storage/tasks/manual_pdf/metadata.json
```

重点检查：

- `input_type` 应为 `pdf`。
- `source_pdf` 应指向原始 PDF。
- `rendered_page_count` 应等于实际输出图片数。
- `total_pdf_pages` 应等于 PDF 总页数。
- 每个 `pages[]` 项应包含 `page_no`、`image_path`、`width`、`height`、`dpi`、`source_type`。
- PDF 页面 `source_type` 应为 `pdf_page`。
- `dpi` 默认应为 `200`。

## 4. 验证二：单张 JPG 转标准页面图

### 4.1 执行命令

```bash
python backend/scripts/render_pdf_pages.py pdfs/complexLayout.jpg --task-id manual_complex_image --overwrite
```

### 4.2 预期命令输出

```text
Rendered 1 page(s).
Task ID: manual_complex_image
Output: backend/storage/tasks/manual_complex_image
Metadata: backend/storage/tasks/manual_complex_image/metadata.json
```

### 4.3 检查输出文件

```bash
find backend/storage/tasks/manual_complex_image -maxdepth 2 -type f
```

应包含：

```text
backend/storage/tasks/manual_complex_image/input/complexLayout.jpg
backend/storage/tasks/manual_complex_image/metadata.json
backend/storage/tasks/manual_complex_image/pages/page_001.png
```

### 4.4 检查图片格式

```bash
file backend/storage/tasks/manual_complex_image/pages/page_001.png
```

预期：

```text
PNG image data, 1080 x 2400, 8-bit/color RGB, non-interlaced
```

实际尺寸以源图为准。

### 4.5 检查 metadata

```bash
sed -n '1,220p' backend/storage/tasks/manual_complex_image/metadata.json
```

重点检查：

- `input_type` 应为 `image`。
- `rendered_page_count` 应为 `1`。
- `total_pdf_pages` 应为 `null`。
- `dpi` 应为 `null`。
- `source_files` 应只有 `pdfs/complexLayout.jpg`。
- `pages[0].source_type` 应为 `image`。
- `pages[0].source_path` 应为 `pdfs/complexLayout.jpg`。

## 5. 验证三：图片目录转连续页面

### 5.1 执行命令

```bash
python backend/scripts/render_pdf_pages.py pdfs --task-id manual_image_dir --overwrite
```

### 5.2 预期命令输出

```text
Rendered 4 page(s).
Task ID: manual_image_dir
Output: backend/storage/tasks/manual_image_dir
Metadata: backend/storage/tasks/manual_image_dir/metadata.json
```

当前 `pdfs/` 目录下有 4 张支持的图片：

```text
complexLayout.jpg
handwrite.jpg
poet.jpg
table.jpg
```

如果目录中新增图片，实际页数会随之变化。

### 5.3 检查输出文件

```bash
find backend/storage/tasks/manual_image_dir/pages -maxdepth 1 -type f
```

应看到连续页面：

```text
backend/storage/tasks/manual_image_dir/pages/page_001.png
backend/storage/tasks/manual_image_dir/pages/page_002.png
backend/storage/tasks/manual_image_dir/pages/page_003.png
backend/storage/tasks/manual_image_dir/pages/page_004.png
```

### 5.4 检查 metadata

```bash
sed -n '1,260p' backend/storage/tasks/manual_image_dir/metadata.json
```

重点检查：

- `input_type` 应为 `image_directory`。
- `rendered_page_count` 应等于图片数量。
- 顶层应包含 `quality_summary`。
- `source_files` 应列出参与转换的图片。
- `pages[]` 中的 `page_no` 应从 1 连续递增。
- `pages[]` 中的 `image_path` 应对应 `page_001.png`、`page_002.png` 等。
- 每页 `source_path` 应能追溯到原始图片。
- 每页应包含 `quality` 字段。

当前按文件名排序，预期顺序为：

```text
page_001.png <- pdfs/complexLayout.jpg
page_002.png <- pdfs/handwrite.jpg
page_003.png <- pdfs/poet.jpg
page_004.png <- pdfs/table.jpg
```

## 6. 验证四：指定 PDF 页码范围

### 6.1 执行命令

```bash
python backend/scripts/render_pdf_pages.py pdfs/pdf1.0.pdf --task-id manual_pdf_pages --pages 1-2 --overwrite
```

### 6.2 预期结果

- `rendered_page_count` 应为 `2`。
- 只生成 `page_001.png` 和 `page_002.png`。
- `metadata.json` 中 `total_pdf_pages` 仍应记录 PDF 原始总页数。

检查：

```bash
find backend/storage/tasks/manual_pdf_pages/pages -maxdepth 1 -type f
sed -n '1,220p' backend/storage/tasks/manual_pdf_pages/metadata.json
```

## 7. 验证五：图片输入禁止使用页码范围

### 7.1 执行命令

```bash
python backend/scripts/render_pdf_pages.py pdfs/complexLayout.jpg --task-id manual_invalid_pages --pages 1 --overwrite
```

### 7.2 预期结果

命令应失败，并提示：

```text
Render failed: --pages can only be used with PDF inputs.
```

这是预期行为，因为图片输入没有 PDF 页码概念。

## 8. 验证六：重复 task_id 的保护

### 8.1 第一次执行

```bash
python backend/scripts/render_pdf_pages.py pdfs/poet.jpg --task-id manual_no_overwrite --overwrite
```

应成功。

### 8.2 第二次不加 overwrite

```bash
python backend/scripts/render_pdf_pages.py pdfs/poet.jpg --task-id manual_no_overwrite
```

应失败，并提示任务目录已存在，需要使用 `--overwrite` 或换一个 `--task-id`。

这个验证用于确认脚本不会意外覆盖已有任务结果。

## 9. 人工目视检查

建议用系统图片查看器打开以下图片：

```text
backend/storage/tasks/manual_complex_image/pages/page_001.png
backend/storage/tasks/manual_image_dir/pages/page_001.png
backend/storage/tasks/manual_image_dir/pages/page_002.png
backend/storage/tasks/manual_image_dir/pages/page_003.png
backend/storage/tasks/manual_image_dir/pages/page_004.png
```

检查重点：

- 页面方向是否正确。
- 文字是否清晰。
- 是否出现明显裁剪。
- 是否出现整页黑屏、白屏或严重变色。
- 复杂公众号截图、手写笔记、诗词页、表格页是否都能正常打开。

## 10. 通过标准

满足以下条件即可认为页面转换增强功能通过手动验证：

- PDF 能按页输出 PNG。
- 单张图片能输出为 `page_001.png`。
- 图片目录能输出连续页面图。
- 输出 PNG 为 RGB。
- `metadata.json` 能准确追溯源文件和页面信息。
- `metadata.json` 包含 `quality_summary` 和每页 `quality` 字段。
- `--pages` 只对 PDF 生效。
- 未加 `--overwrite` 时不会覆盖已有任务。
- 目视检查页面方向、清晰度和完整性无明显问题。

## 11. 常见问题

### 11.1 处理 PDF 时提示 PyMuPDF 未安装

说明当前 Python 环境没有安装 `pymupdf`。安装：

```bash
pip install pymupdf
```

如果使用 Conda 环境，先激活项目环境后再安装。

### 11.2 图片目录输出顺序不符合预期

当前按文件名升序排序。如果需要自定义顺序，可以重命名图片，例如：

```text
001_complexLayout.jpg
002_handwrite.jpg
003_poet.jpg
004_table.jpg
```

### 11.3 图片太小导致后续 OCR 效果差

页面转换阶段不会主动放大图片。后续可以增加“图像质量检查”模块，在 metadata 中标记过小、过暗、低对比度图片，再决定是否增强。
