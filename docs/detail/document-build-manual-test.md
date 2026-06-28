# 文本清理与文档结构构建手动验证文档

## 1. 验证目标

本阶段验证 `backend/scripts/build_document.py` 是否能把 OCR 输出转换为可阅读、可导出的中间文档结构。

输入：

- `backend/storage/tasks/{task_id}/ocr/page_*.json`

输出：

- `backend/storage/tasks/{task_id}/clean/document.json`
- `backend/storage/tasks/{task_id}/clean/book.md`

当前版本采用保守策略：

- 按 layout/OCR 中的 `order` 排序文本块。
- 合并同一 OCR block 内的多行文本。
- 将 `title/subtitle/body/caption/sidebar/note` 转换为统一文档块。
- 保留来源页、来源 layout block、坐标和 OCR 置信度。
- 生成页面结构、章节结构和 Markdown 调试稿。
- 暂不做激进的跨页段落拼接，避免复杂杂志页面被误合并。

## 2. 环境要求

统一使用 conda 环境：

```bash
conda run -n industrial-cv python ...
```

语法检查：

```bash
conda run -n industrial-cv python -m py_compile backend/scripts/build_document.py
```

## 3. 基本运行命令

图片样例任务：

```bash
conda run -n industrial-cv python backend/scripts/build_document.py layout_step1_images
```

PDF 样例任务：

```bash
conda run -n industrial-cv python backend/scripts/build_document.py layout_step1_pdf
```

## 4. 当前验证结果

### 4.1 图片样例任务

命令：

```bash
conda run -n industrial-cv python backend/scripts/build_document.py layout_step1_images
```

结果：

```text
Built document for task: layout_step1_images
Title: layout_step1_images
Pages: 4
Blocks: 42
Headings: 6
Paragraphs: 36
Captions: 0
Document JSON: backend/storage/tasks/layout_step1_images/clean/document.json
Markdown: backend/storage/tasks/layout_step1_images/clean/book.md
```

结构校验：

```text
pages 4
chapters 3
page_blocks 42
markdown_exists True
markdown_size 4065
bad_source_pages 0
missing_fields 0
```

说明：

- 复杂公众号截图、手写页、诗词页、简历页都能进入统一文档结构。
- 手写页 OCR 结果仍可能不稳定，这是 OCR 质量问题，不在本层强行修正。
- 当前标题推断较保守，复杂首页默认使用任务 ID，避免把杂志短句误判为书名。

### 4.2 PDF 样例任务

命令：

```bash
conda run -n industrial-cv python backend/scripts/build_document.py layout_step1_pdf
```

结果：

```text
Built document for task: layout_step1_pdf
Title: layout_step1_pdf
Pages: 6
Blocks: 49
Headings: 7
Paragraphs: 38
Captions: 4
Document JSON: backend/storage/tasks/layout_step1_pdf/clean/document.json
Markdown: backend/storage/tasks/layout_step1_pdf/clean/book.md
```

结构校验：

```text
pages 6
chapters 5
page_blocks 49
markdown_exists True
markdown_size 15226
bad_source_pages 0
missing_fields 0
```

说明：

- PDF 样例能生成可阅读 Markdown。
- 标题、正文、图注能区分输出。
- 每个输出 block 都保留 `source_pages` 和 `source_block_ids`，后续可以追溯到 OCR 和 layout 结果。

## 5. 结构校验命令

可以用下面的命令检查输出完整性：

```bash
conda run -n industrial-cv python -c 'import json, pathlib
for task in ["layout_step1_images", "layout_step1_pdf"]:
    base = pathlib.Path("backend/storage/tasks") / task
    doc_path = base / "clean" / "document.json"
    md_path = base / "clean" / "book.md"
    doc = json.loads(doc_path.read_text(encoding="utf-8"))
    page_block_total = sum(len(p["blocks"]) for p in doc["pages"])
    bad_source_pages = []
    missing_fields = []
    for page in doc["pages"]:
        for block in page["blocks"]:
            if page["page_no"] not in block.get("source_pages", []):
                bad_source_pages.append((page["page_no"], block.get("id")))
            for field in ["id", "type", "text", "source_pages", "source_block_ids"]:
                if field not in block:
                    missing_fields.append((block.get("id"), field))
    print("TASK", task)
    print("title", doc["title"])
    print("stats", doc["stats"])
    print("pages", len(doc["pages"]), "chapters", len(doc["chapters"]), "page_blocks", page_block_total)
    print("markdown_exists", md_path.exists(), "markdown_size", md_path.stat().st_size)
    print("bad_source_pages", len(bad_source_pages), "missing_fields", len(missing_fields))
    print()
'
```

## 6. 手动检查清单

检查 `clean/book.md`：

- 页面顺序是否正确。
- 正文是否不再按 OCR 行硬断开。
- 标题是否以 `#` 或 `##` 输出。
- 图注是否以引用块 `>` 输出。
- 页眉、页脚、页码是否没有进入正文。
- 手写、复杂排版页面是否至少保留了可追溯文本。

检查 `clean/document.json`：

- 顶层是否包含 `task_id/title/language/stats/pages/chapters`。
- 每个 block 是否包含 `id/type/text/source_pages/source_block_ids`。
- `ocr_confidence`、`bbox`、`order` 是否保留下来。
- `chapters` 是否能作为后续 EPUB 目录基础。

## 7. 当前边界

- 暂不跨页强制拼段，防止杂志多栏页面被误合并。
- 暂不对 OCR 错字做语义纠错，避免引入模型幻觉。
- 暂不把表格恢复成 Markdown 表格，表格块后续进入单独模块处理。
- 复杂页面的图文解释仍留给第三层 VLM 兜底。

## 8. 下一步

本层完成后，可以继续做两件事：

- EPUB 导出：读取 `clean/document.json`，生成章节 XHTML、目录和元数据。
- 段落增强：在可控规则下补充跨页拼段、章节标题正则识别、英文断词修复。
