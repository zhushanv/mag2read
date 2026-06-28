# OCR 模块手动验证文档

## 1. 验证目标

验证 OCR 模块能基于第二层 `layout/page_xxx.json`，只对文本类版面块进行 OCR，并输出与 `block_id` 对齐的 OCR JSON。

OCR 模块输入：

```text
backend/storage/tasks/{task_id}/layout/page_xxx.json
backend/storage/tasks/{task_id}/pages/page_xxx.png
```

OCR 模块输出：

```text
backend/storage/tasks/{task_id}/ocr/page_xxx.json
backend/storage/tasks/{task_id}/ocr/summary.json
```

## 2. 运行环境

进入项目根目录：

```bash
cd /Users/zhu/projects/python-project/课程项目2
```

统一使用 `industrial-cv` 环境：

```bash
conda run -n industrial-cv python ...
```

## 3. 测试前准备

确认脚本语法：

```bash
conda run -n industrial-cv python -m py_compile backend/scripts/run_ocr.py
```

预期：无输出，退出码为 0。

OCR 依赖第二层输出。如果任务还没有 `layout/`，需要先执行：

```bash
conda run -n industrial-cv python backend/scripts/render_pdf_pages.py pdfs --task-id manual_ocr_images --overwrite
conda run -n industrial-cv python backend/scripts/analyze_layout.py manual_ocr_images
conda run -n industrial-cv python backend/scripts/refine_layout.py manual_ocr_images
```

## 4. 验证一：图片目录样例

### 4.1 执行 OCR

```bash
conda run -n industrial-cv python backend/scripts/run_ocr.py manual_ocr_images
```

预期输出类似：

```text
OCR processed 4 page(s).
Task ID: manual_ocr_images
OCR blocks: ...
Recognized blocks: ...
Lines: ...
Average confidence: ...
Summary: backend/storage/tasks/manual_ocr_images/ocr/summary.json
```

### 4.2 检查输出文件

```bash
find backend/storage/tasks/manual_ocr_images/ocr -maxdepth 1 -type f | sort
```

应包含：

```text
page_001.json
page_002.json
page_003.json
page_004.json
summary.json
```

### 4.3 检查 summary

```bash
sed -n '1,260p' backend/storage/tasks/manual_ocr_images/ocr/summary.json
```

重点检查：

- `page_count`
- `ocr_block_count`
- `recognized_block_count`
- `skipped_block_count`
- `line_count`
- `avg_confidence`
- `low_confidence_block_count`
- `role_counts`

## 5. 验证二：PDF 样例

### 5.1 准备任务

```bash
conda run -n industrial-cv python backend/scripts/render_pdf_pages.py pdfs/pdf1.0.pdf --task-id manual_ocr_pdf --overwrite
conda run -n industrial-cv python backend/scripts/analyze_layout.py manual_ocr_pdf
conda run -n industrial-cv python backend/scripts/refine_layout.py manual_ocr_pdf
```

### 5.2 执行 OCR

```bash
conda run -n industrial-cv python backend/scripts/run_ocr.py manual_ocr_pdf
```

预期：

- `ocr/page_001.json` 到 `ocr/page_006.json` 均生成。
- `ocr/summary.json` 中 `page_count = 6`。
- PDF 样例平均置信度应明显高于手写样例。

## 6. OCR 输出结构检查

执行：

```bash
conda run -n industrial-cv python -c "import json; from pathlib import Path
errors=[]
for task in ['manual_ocr_images','manual_ocr_pdf']:
  layout_blocks={}
  for p in Path(f'backend/storage/tasks/{task}/layout').glob('page_*.json'):
    d=json.loads(p.read_text())
    layout_blocks.update({b['block_id']: b for b in d['blocks']})
  for p in Path(f'backend/storage/tasks/{task}/ocr').glob('page_*.json'):
    d=json.loads(p.read_text())
    for b in d['blocks']:
      if b['block_id'] not in layout_blocks: errors.append(f'{task}:{p.name}:{b[\"block_id\"]} missing layout source')
      for key in ['block_id','page_no','role','text','ocr_confidence','bbox','column','order','reading_group','lines']:
        if key not in b: errors.append(f'{task}:{p.name}:{b.get(\"block_id\")}: missing {key}')
      if b['ocr_confidence'] is None and b['text']: errors.append(f'{task}:{p.name}:{b[\"block_id\"]}: text without confidence')
print('errors', len(errors))
for e in errors[:20]: print(e)"
```

预期：

```text
errors 0
```

## 7. 单页 OCR JSON 检查

查看第一页：

```bash
sed -n '1,220p' backend/storage/tasks/manual_ocr_images/ocr/page_001.json
```

每个 OCR block 应包含：

```json
{
  "block_id": "p001_b0001",
  "page_no": 1,
  "role": "body",
  "raw_type": "text",
  "text": "识别文本",
  "ocr_confidence": 0.9935,
  "bbox": {},
  "column": 1,
  "order": 2,
  "reading_group": "main",
  "layout_confidence": {},
  "line_count": 4,
  "lines": []
}
```

每个 `lines[]` 应包含：

```json
{
  "line_no": 1,
  "text": "单行文本",
  "confidence": 0.98,
  "bbox": {
    "x1": 131.0,
    "y1": 750.0,
    "x2": 898.0,
    "y2": 768.0
  },
  "polygon": []
}
```

坐标应已经从裁剪图坐标还原为页面坐标。

## 8. 当前已验证结果

当前已验证任务：

```text
layout_step1_images
layout_step1_pdf
```

### 8.1 layout_step1_images

```text
pages: 4
ocr_blocks: 42
recognized: 42
skipped: 17
lines: 211
avg_confidence: 0.9448
low_confidence_block_count: 8
role_counts: {'body': 36, 'title': 2, 'subtitle': 4}
```

逐页：

```text
page 1: blocks 21, lines 31, confidence 0.9749
page 2: blocks 17, lines 155, confidence 0.8438
page 3: blocks 2,  lines 23, confidence 0.9604
page 4: blocks 2,  lines 2,  confidence 1.0
```

说明：

- `complexLayout.jpg` 识别效果较好。
- `handwrite.jpg` 能跑通，但平均置信度较低，这是手写内容的预期风险。
- `table.jpg` 中表格区域被跳过，只 OCR 标题/正文文本块。

### 8.2 layout_step1_pdf

```text
pages: 6
ocr_blocks: 49
recognized: 49
skipped: 15
lines: 401
avg_confidence: 0.9938
low_confidence_block_count: 0
role_counts: {'body': 38, 'title': 4, 'caption': 4, 'subtitle': 3}
```

逐页：

```text
page 1: blocks 8,  lines 63, confidence 0.9892
page 2: blocks 6,  lines 55, confidence 0.9935
page 3: blocks 12, lines 65, confidence 0.996
page 4: blocks 8,  lines 59, confidence 0.9957
page 5: blocks 6,  lines 72, confidence 0.9945
page 6: blocks 9,  lines 87, confidence 0.994
```

## 9. 可选参数

### 9.1 保存裁剪图

```bash
conda run -n industrial-cv python backend/scripts/run_ocr.py manual_ocr_images --save-crops
```

会保留：

```text
backend/storage/tasks/{task_id}/ocr_crops/
```

用于检查某个 block 的 OCR 输入区域。

### 9.2 OCR unknown 块

```bash
conda run -n industrial-cv python backend/scripts/run_ocr.py manual_ocr_images --include-unknown
```

默认不 OCR `unknown`，开启后会尝试识别。

### 9.3 启用文字行方向模型

```bash
conda run -n industrial-cv python backend/scripts/run_ocr.py manual_ocr_images --use-textline-orientation
```

这个参数可能需要额外下载 PaddleOCR 文字行方向模型。普通横排文档第一版不建议默认开启。

## 10. 通过标准

满足以下条件即可认为 OCR 模块通过：

- `run_ocr.py` 语法检查通过。
- 能读取 `layout/page_xxx.json`。
- 能输出 `ocr/page_xxx.json` 和 `ocr/summary.json`。
- OCR block 的 `block_id` 能追溯到 layout block。
- 默认跳过 `figure/table/formula/header/footer/page_number/adornment`。
- 所有识别文本包含 `ocr_confidence`。
- 每行文本包含页面坐标系下的 `bbox` 或 `polygon`。
- PDF 样例平均置信度较高。
- 手写样例可以识别但允许低置信度，后续进入专门手写策略。

## 11. 下一步

OCR 完成后，下一步进入文本清洗和文档结构构建：

- 按 layout `order` 排序 OCR block。
- 过滤噪音块。
- 合并同一段落的多行文本。
- 保留标题、图注、边栏等结构。
- 输出 `clean/document.json` 和 `clean/book.md`。
