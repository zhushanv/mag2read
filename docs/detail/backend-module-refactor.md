# 后端模块化整理说明

## 1. 整理目标

本次整理把原来集中放在 `backend/scripts` 下的流程脚本拆成可调用模块，同时保留原有命令行入口。

目标不是做一个大而全的 Pipeline 类，而是保持每个流程都能单独调用、单独测试、单独优化。

## 2. 当前目录结构

```text
backend/
  app/
    core/
      paths.py
      io.py
    modules/
      render.py
      layout_detect.py
      layout_refine.py
      ocr.py
      text_cleaning.py
      document_build.py
      export_document.py
    pipeline/
      task_runner.py
  scripts/
    render_pdf_pages.py
    analyze_layout.py
    refine_layout.py
    run_ocr.py
    clean_text.py
    build_document.py
    export_document.py
  过程备份/
```

## 3. 模块职责

| 模块 | 职责 |
| --- | --- |
| `backend.app.modules.render` | PDF/图片输入转标准页面 PNG，并做图像质量检查 |
| `backend.app.modules.layout_detect` | 第一层 PP-DocLayout/LayoutDetection 版面检测 |
| `backend.app.modules.layout_refine` | 第二层自定义规则修正版面结构 |
| `backend.app.modules.ocr` | 对文本类 layout block 执行 OCR |
| `backend.app.modules.text_cleaning` | 页眉页脚过滤、断词修复、跨页拼接、段落边界识别 |
| `backend.app.modules.document_build` | 从 `clean/document.json` 补章节结构并生成 Markdown |
| `backend.app.modules.export_document` | 从清洗后文档导出 EPUB、DOCX、TXT、HTML |

## 4. 调用方式

### 4.1 单模块调用

后续优化单个流程时，优先直接调用模块函数。

示例：

```python
from pathlib import Path
from backend.app.modules.layout_refine import refine_task_layout

summary = refine_task_layout(Path("backend/storage/tasks/demo_task"))
```

OCR 示例：

```python
from pathlib import Path
from backend.app.modules.ocr import run_task_ocr
from backend.app.core.paths import PADDLEX_CACHE_ROOT

summary = run_task_ocr(
    task_dir=Path("backend/storage/tasks/demo_task"),
    cache_dir=PADDLEX_CACHE_ROOT,
    padding=4,
    include_unknown=False,
    save_crops=False,
    use_textline_orientation=False,
)
```

### 4.2 保留命令行入口

原命令仍然保留：

```bash
conda run -n industrial-cv python backend/scripts/render_pdf_pages.py pdfs/poet.jpg --task-id demo --overwrite
conda run -n industrial-cv python backend/scripts/analyze_layout.py demo
conda run -n industrial-cv python backend/scripts/refine_layout.py demo
conda run -n industrial-cv python backend/scripts/run_ocr.py demo
conda run -n industrial-cv python backend/scripts/clean_text.py demo
conda run -n industrial-cv python backend/scripts/build_document.py demo
conda run -n industrial-cv python backend/scripts/export_document.py demo --formats epub,html
```

这些脚本现在只是 wrapper，真正逻辑在 `backend/app/modules`。

### 4.3 轻量编排器

`backend.app.pipeline.task_runner` 提供串联入口，但不替代单步模块。

```python
from backend.app.pipeline.task_runner import PipelineConfig, run_existing_task

results = run_existing_task(
    "demo",
    stages=["layout_detect", "layout_refine", "ocr", "text_cleaning", "document_build"],
    config=PipelineConfig(),
)
```

## 5. 过程备份

本次整理移动到备份的内容：

- `backend/.DS_Store`
- `backend/scripts/__pycache__`
- 本次烟测生成的 `module_refactor_smoke_render`
- 误建的空英文备份目录 `backend/process_backup`

备份位置：

```text
backend/过程备份/20260627_module_refactor/
```

## 6. 验证结果

已完成：

- `backend/app/core/*.py` 编译通过。
- `backend/app/modules/*.py` 编译通过。
- `backend/app/pipeline/*.py` 编译通过。
- `backend/scripts/*.py` 编译通过。
- 核心模块导入通过。
- `task_runner` 导入通过。
- `render_pdf_pages.py` wrapper 能正常渲染图片输入。

注意：

- 当前 active 的 `backend/storage/tasks` 目录没有完整历史任务输出。
- 历史任务已在 `backend/过程备份/storage/tasks` 下，因此没有继续执行 OCR/清洗/导出端到端回归。
