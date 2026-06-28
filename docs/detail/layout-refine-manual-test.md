# 第二层版面规则修正手动验证文档

## 1. 验证目标

验证第二层规则引擎能把第一层 `layout_raw/page_xxx.json` 转换为下游统一使用的 `layout/page_xxx.json`。

第二层负责：

- `raw_type -> role` 映射。
- `reading_group` 标记。
- 页眉、页脚、底部装饰文字等噪音修正。
- 手写页中 `formula -> body` 重分类。
- 单栏、双栏、复杂混排判断。
- 初步阅读顺序 `order`。
- 页面类型 `page_type`。
- 复杂度评分和 `need_vlm`。

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
conda run -n industrial-cv python -m py_compile backend/scripts/refine_layout.py
```

预期：无输出，退出码为 0。

第二层依赖第一层输出，因此任务目录中必须已有：

```text
backend/storage/tasks/{task_id}/layout_raw/page_001.json
backend/storage/tasks/{task_id}/layout_raw/summary.json
```

如果没有，先运行第一层：

```bash
conda run -n industrial-cv python backend/scripts/analyze_layout.py {task_id}
```

## 4. 验证一：图片目录样例

### 4.1 生成页面图

```bash
conda run -n industrial-cv python backend/scripts/render_pdf_pages.py pdfs --task-id manual_refine_images --overwrite
```

### 4.2 生成第一层 layout_raw

```bash
conda run -n industrial-cv python backend/scripts/analyze_layout.py manual_refine_images
```

### 4.3 执行第二层规则修正

```bash
conda run -n industrial-cv python backend/scripts/refine_layout.py manual_refine_images
```

预期输出：

```text
Refined 4 page(s).
Task ID: manual_refine_images
Need VLM pages: 1
Summary: backend/storage/tasks/manual_refine_images/layout/summary.json
```

### 4.4 检查输出文件

```bash
find backend/storage/tasks/manual_refine_images/layout -maxdepth 1 -type f | sort
```

应包含：

```text
page_001.json
page_002.json
page_003.json
page_004.json
summary.json
```

### 4.5 检查 summary

```bash
sed -n '1,260p' backend/storage/tasks/manual_refine_images/layout/summary.json
```

当前 `pdfs/` 图片目录样例的参考结果：

```text
page_001 complexLayout.jpg -> magazine_complex / mixed_complex / need_vlm=true
page_002 handwrite.jpg     -> handwriting / single_column / need_vlm=false
page_003 poet.jpg          -> book_text / single_column / need_vlm=false
page_004 table.jpg         -> form_or_resume / image_dominant / need_vlm=false
```

## 5. 验证二：PDF 样例

### 5.1 生成页面图

```bash
conda run -n industrial-cv python backend/scripts/render_pdf_pages.py pdfs/pdf1.0.pdf --task-id manual_refine_pdf --overwrite
```

### 5.2 生成第一层 layout_raw

```bash
conda run -n industrial-cv python backend/scripts/analyze_layout.py manual_refine_pdf
```

### 5.3 执行第二层规则修正

```bash
conda run -n industrial-cv python backend/scripts/refine_layout.py manual_refine_pdf
```

预期：

- `layout/page_001.json` 到 `layout/page_006.json` 均生成。
- `layout/summary.json` 中 `page_count = 6`。
- `need_vlm_page_count` 允许大于 0，复杂图文页应被标记。

## 6. 结构完整性检查

执行：

```bash
conda run -n industrial-cv python -c "import json; from pathlib import Path
errors=[]
for task in ['manual_refine_images','manual_refine_pdf']:
  for path in sorted(Path(f'backend/storage/tasks/{task}/layout').glob('page_*.json')):
    data=json.loads(path.read_text())
    for key in ['task_id','page_no','image_path','width','height','page_type','layout_type','complexity','blocks']:
      if key not in data: errors.append(f'{path}: missing {key}')
    for b in data['blocks']:
      for key in ['block_id','source','raw_id','raw_type','role','bbox','confidence','column','order','reading_group','is_noise','notes']:
        if key not in b: errors.append(f'{path}:{b.get(\"block_id\")}: missing {key}')
      if not b['is_noise'] and b['order'] is None: errors.append(f'{path}:{b[\"block_id\"]}: non-noise block has no order')
      if b['is_noise'] and b['order'] is not None: errors.append(f'{path}:{b[\"block_id\"]}: noise block has order')
print('errors', len(errors))
for e in errors[:20]: print(e)"
```

预期：

```text
errors 0
```

## 7. 重点字段检查

### 7.1 页面级字段

每个 `layout/page_xxx.json` 应包含：

```json
{
  "page_type": "magazine_complex",
  "layout_type": "mixed_complex",
  "complexity": {
    "level": "high",
    "score": 0.75,
    "need_vlm": true,
    "reasons": []
  }
}
```

### 7.2 区块级字段

每个 block 应包含：

```json
{
  "block_id": "p001_b0001",
  "source": "rule_mapped",
  "raw_id": "p001_raw_0001",
  "raw_type": "text",
  "role": "body",
  "confidence": {
    "detector": 0.9824,
    "rule": 0.85,
    "final": 0.9162
  },
  "column": 1,
  "order": 1,
  "reading_group": "main",
  "is_noise": false,
  "notes": []
}
```

## 8. 当前已验证结果

当前已验证任务：

```text
layout_step1_images
layout_step1_pdf
```

`layout_step1_images` 结果：

```text
page_count: 4
need_vlm_page_count: 1
page_type_counts:
  magazine_complex: 1
  handwriting: 1
  book_text: 1
  form_or_resume: 1
layout_type_counts:
  mixed_complex: 1
  single_column: 2
  image_dominant: 1
```

逐页结果：

```text
page 1: magazine_complex / mixed_complex / need_vlm=true
page 2: handwriting / single_column / need_vlm=false
page 3: book_text / single_column / need_vlm=false
page 4: form_or_resume / image_dominant / need_vlm=false
```

`layout_step1_pdf` 结果：

```text
page_count: 6
need_vlm_page_count: 2
```

其中复杂图文页会被标记为 `need_vlm=true`，后续交给第三层视觉模型处理。

## 9. 通过标准

满足以下条件即可认为第二层规则修正通过：

- `refine_layout.py` 语法检查通过。
- 能读取 `layout_raw/page_xxx.json`。
- 能输出 `layout/page_xxx.json`。
- 能输出 `layout/summary.json`。
- 所有非噪音块都有 `order`。
- 噪音块没有 `order`。
- 手写样例能识别为 `handwriting`，且 `formula` 被重分类为 `body`。
- 复杂截图能识别为 `magazine_complex`，且 `need_vlm=true`。
- 表格样例能识别为 `form_or_resume`。
- 诗词样例能识别为 `book_text` 或简单文本页。

## 10. 下一步

第二层完成后，下一步可以进入 OCR 模块：

- 读取 `layout/page_xxx.json`。
- 只对 `title`、`subtitle`、`body`、`caption`、`sidebar` 等文本块 OCR。
- 默认跳过 `header`、`footer`、`page_number`、`adornment`。
- 对 `figure`、`table`、`formula` 保留占位或进入后续专门处理。
