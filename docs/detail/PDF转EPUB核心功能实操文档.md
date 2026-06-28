# PDF/图片转 EPUB 核心功能实操文档

## 1. 目标与边界

本项目的目标是把用户上传的 PDF、JPG、PNG 文件，经过版面分析、OCR、文本清洗、章节组织后，导出为可阅读的 EPUB 和便于二次编辑的 Markdown。

第一阶段先实现核心闭环：

```text
文件上传 -> 页面预处理 -> 分层版面分析 -> OCR识别 -> 文本清洗 -> Markdown导出 -> EPUB导出
```

暂不优先处理复杂能力：

- 不先做用户系统、权限系统和在线书库。
- 不先追求复杂公式、复杂表格的完美还原。
- 不先做大规模并发任务调度。
- 不先让视觉大模型接管所有页面，只对复杂杂志页和低置信度页面预留兜底能力。

## 2. MVP 功能范围

### 2.1 必须实现

| 模块 | MVP 要求 | 优先级 |
|---|---|---|
| 文件上传与管理 | 支持 PDF、JPG、PNG 上传，单文件不超过 50MB，保存任务记录和文件列表 | P0 |
| 页面转换 | PDF 拆成图片页，图片文件统一转为标准页面图 | P0 |
| 分层版面分析 | 使用 PP-DocLayout 检测页面区域，并输出统一 layout JSON | P0 |
| 规则修正与阅读顺序 | 修正标题、正文、图注、页眉页脚页码，判断单栏/双栏/多栏，生成阅读顺序 | P0 |
| OCR 识别 | 基于 layout JSON 对文本区块 OCR，输出文字、置信度、坐标、页码和所属版面块 | P0 |
| 文本清洗 | 过滤页眉、页脚、页码，合并断行和跨页段落 | P1 |
| Markdown 导出 | 导出清洗后的章节文本，便于人工编辑 | P0 |
| EPUB 导出 | 导出标准 EPUB，包含书名、作者、目录和正文 | P0 |
| AI 导读 | 生成 200 字摘要和 3-5 个关键词，写入元数据或单独页面 | P1 |

### 2.2 后续再做

| 模块 | 说明 | 优先级 |
|---|---|---|
| 复杂页视觉兜底 | 对复杂杂志页调用 Qwen-VL 或 GPT-4o-mini 修正阅读顺序、图文关系和图片摘要 | P2 |
| 高质量表格还原 | 表格导出为 Markdown 表格或 HTML 表格 | P2 |
| 人工校对后台 | 支持编辑 OCR 结果、调整章节、删除噪音 | P2 |
| 批量任务队列 | 支持多个大文件异步转换和失败重试 | P2 |

## 3. 技术选型

### 3.1 后端主流程

| 环节 | 推荐工具 | 说明 |
|---|---|---|
| Web 后端 | FastAPI | 轻量，适合文件上传、任务状态查询、导出下载 |
| 静态文件服务 | Nginx | 承担上传文件、导出文件、页面图片的静态访问 |
| PDF 转图片 | PyMuPDF 或 poppler | 将 PDF 按页渲染为图片，推荐 200-300 DPI |
| 第一层版面检测 | PP-DocLayout / PaddleOCR 文档版面模型 | 识别标题、正文、图片、表格、公式、图注等候选区域 |
| 第二层规则引擎 | 自定义 Python 规则 | 修正区域类型、判断栏位、阅读顺序、页眉页脚页码和复杂度 |
| OCR | PaddleOCR | 基于 layout JSON 对文本块识别，输出文字与坐标 |
| 文本清洗 | Python 规则引擎 | 基于 layout、坐标、正则、页码、重复文本规则清洗 |
| EPUB 生成 | EbookLib | 后端内直接生成 EPUB，便于控制元数据和章节 |
| Markdown 导出 | Python 模板拼接 | 结构简单，便于人工编辑 |
| AI 摘要 | DeepSeek API | 对清洗后的正文生成摘要和关键词 |
| 复杂页视觉兜底 | Qwen-VL 或 GPT-4o-mini | 只处理复杂页面的阅读顺序、图文关系和视觉摘要 |

### 3.2 为什么 EPUB 用 EbookLib 优先

Pandoc 适合从 Markdown、DOCX、HTML 转 EPUB，但在后端服务里直接生成标准 EPUB 时，EbookLib 更方便控制章节、元数据、封面、目录和资源文件。

建议策略：

- 第一版：`清洗文本 -> Markdown -> EbookLib -> EPUB`
- 调试版：保留 Markdown 下载，方便检查 OCR 和清洗效果。
- 精修版：可以再引入 Pandoc，把人工修订后的 Markdown 转成 EPUB。

## 4. 系统处理流程

### 4.1 总体流程

```text
用户上传文件
  |
  v
创建转换任务
  |
  v
文件类型判断
  |
  +-- PDF -> 按页渲染为图片
  |
  +-- JPG/PNG -> 统一转为页面图片
  |
  v
PP-DocLayout 原始版面检测
  |
  v
规则修正、栏位判断、复杂度评分
  |
  +-- 普通页 -> 直接进入 OCR
  |
  +-- 复杂页 -> 视觉大模型兜底后再进入 OCR
  |
  v
OCR 识别并输出坐标 JSON
  |
  v
过滤页眉、页脚、页码等噪音
  |
  v
合并段落、识别标题层级
  |
  v
生成 Markdown
  |
  v
生成 EPUB
  |
  v
返回下载链接和任务状态
```

### 4.2 任务状态设计

任务状态建议保持简单：

| 状态 | 含义 |
|---|---|
| `uploaded` | 文件已上传 |
| `preprocessing` | 正在拆页、转图片 |
| `layout_detecting` | 正在进行 PP-DocLayout 原始版面检测 |
| `layout_refining` | 正在进行规则修正、栏位判断和阅读顺序排序 |
| `vlm_analyzing` | 正在对复杂页面调用视觉大模型兜底 |
| `ocr_running` | 正在 OCR |
| `cleaning` | 正在清洗和拼段 |
| `exporting` | 正在生成 Markdown/EPUB |
| `finished` | 转换完成 |
| `failed` | 转换失败 |

每个任务至少记录：

- `task_id`
- `original_filename`
- `file_type`
- `file_size`
- `page_count`
- `status`
- `progress`
- `layout_summary`
- `complex_page_count`
- `error_message`
- `created_at`
- `updated_at`
- `markdown_path`
- `epub_path`

## 5. 数据结构约定

### 5.1 页面级 layout 数据

每一页经过分层版面分析后保存一份统一 layout 信息。后续 OCR、文本清洗和 EPUB 导出都只读取 `layout/page_xxx.json`，不直接依赖模型原始输出。

```json
{
  "task_id": "demo_task",
  "page_no": 1,
  "image_path": "pages/page_001.png",
  "width": 2480,
  "height": 3508,
  "page_type": "magazine_complex",
  "layout_type": "multi_column",
  "complexity": {
    "level": "high",
    "score": 0.82,
    "reasons": [
      "figure_area_ratio_gt_0.4",
      "text_blocks_scattered",
      "more_than_two_columns"
    ],
    "need_vlm": true
  },
  "blocks": []
}
```

### 5.2 版面区块数据

每个区块保留来源、类型、坐标、置信度、阅读顺序和是否进入正文。OCR 后再补充 `text` 字段。

```json
{
  "block_id": "p001_b0001",
  "source": "rule_corrected",
  "raw_type": "text",
  "role": "body",
  "text": "",
  "bbox": {
    "x1": 184,
    "y1": 420,
    "x2": 1120,
    "y2": 860
  },
  "confidence": {
    "detector": 0.91,
    "rule": 0.86,
    "final": 0.88
  },
  "column": 1,
  "order": 7,
  "reading_group": "main",
  "is_noise": false,
  "notes": []
}
```

`role` 建议统一为以下几类：

| role | 含义 | 默认处理 |
|---|---|---|
| `title` | 主标题或章节标题 | 参与目录和章节识别 |
| `subtitle` | 副标题 | 可进入章节开头 |
| `body` | 正文 | 进入 OCR 和 EPUB 正文 |
| `caption` | 图注、表注 | 保留在图片或表格附近 |
| `figure` | 图片、地图、照片 | 第一版保留占位，后续可摘要 |
| `table` | 表格 | 第一版保留占位，后续可结构化 |
| `formula` | 公式 | 保留占位或截图 |
| `header` | 页眉 | 默认过滤 |
| `footer` | 页脚 | 默认过滤 |
| `page_number` | 页码 | 默认过滤 |
| `sidebar` | 边栏、补充阅读 | 可作为附注 |
| `adornment` | 装饰性文字 | 默认不进入正文 |
| `unknown` | 未识别类型 | 保留低置信度标记 |

`reading_group` 建议统一为以下几类：

| reading_group | 含义 |
|---|---|
| `main` | 主阅读流 |
| `caption` | 图注、表注 |
| `sidebar` | 边栏或补充阅读 |
| `note` | 脚注、注释 |
| `visual` | 图片、表格、地图等视觉块 |
| `noise` | 页眉、页脚、页码等噪音 |
| `unknown` | 暂不确定 |

### 5.3 OCR 文本块

OCR 模块不重新发明坐标结构，而是在 layout block 基础上补充识别结果：

```json
{
  "block_id": "p001_b0001",
  "page_no": 1,
  "role": "body",
  "text": "这里是识别出的正文内容。",
  "ocr_confidence": 0.96,
  "bbox": {
    "x1": 184,
    "y1": 420,
    "x2": 1120,
    "y2": 860
  },
  "column": 1,
  "order": 7,
  "reading_group": "main"
}
```

### 5.4 清洗后的文档结构

清洗后不再以 OCR 块为主要单位，而是转成章节和段落：

```json
{
  "title": "文档标题",
  "author": "",
  "summary": "",
  "keywords": [],
  "chapters": [
    {
      "chapter_id": "ch001",
      "title": "第一章 标题",
      "level": 1,
      "paragraphs": [
        {
          "text": "这是一个完整段落。",
          "source_pages": [1, 2]
        }
      ]
    }
  ]
}
```

## 6. 核心模块实操说明

### 6.1 文件上传与管理

目标是稳定接收文件，并能追踪转换进度。

实操要求：

- 前端限制文件类型：`.pdf`、`.jpg`、`.jpeg`、`.png`。
- 后端再次校验 MIME 类型和文件后缀。
- 单文件限制 50MB。
- 上传成功后立即创建 `task_id`。
- 原始文件不要直接覆盖，按任务目录保存。
- 文件名展示用原始文件名，实际存储用安全文件名或 UUID。

建议目录：

```text
storage/
  tasks/
    {task_id}/
      input/
        original.pdf
      pages/
        page_001.png
        page_002.png
      layout_raw/
        page_001.json
        page_002.json
      layout/
        page_001.json
        page_002.json
      vlm/
        page_001.request.json
        page_001.response.json
      debug/
        page_001_layout_overlay.png
      ocr/
        page_001.json
        page_002.json
      clean/
        document.json
        book.md
      export/
        book.epub
```

验收标准：

- 上传 1 个 PDF 后能生成任务记录。
- 上传多张 JPG/PNG 后能按顺序进入同一个任务。
- 超过 50MB 时返回明确错误。
- 前端能看到文件名、大小、状态和进度。

### 6.2 PDF 和图片预处理

目标是把所有输入统一成页面图片。

处理策略：

- PDF：按页渲染成 PNG，建议 200-300 DPI。
- 单张 JPG/PNG：作为一页输入，统一输出为 `pages/page_001.png`。
- 图片目录：按文件名排序，把多张图片统一输出为 `page_001.png`、`page_002.png` 等连续页面。
- JPG/PNG：根据 EXIF 修正方向，检查尺寸和颜色模式，必要时转为 RGB PNG。
- 图片过大时可以等比缩放，但不要低到影响 OCR。
- 记录每页图片宽高，后续坐标规则依赖页面尺寸。
- 在 `metadata.json` 中记录 `input_type`、`source_files`、`source_path`、`source_type`、宽高和 DPI。
- 对每页执行图像质量检查，检测异常方向、超小图、空白页、过暗和低对比度问题。
- 质量检查只写入 metadata，不主动修改图片，避免预处理破坏后续版面分析。

质量检查字段：

```json
{
  "quality": {
    "status": "review",
    "orientation": "portrait",
    "width": 800,
    "height": 1039,
    "pixel_count": 831200,
    "aspect_ratio": 0.77,
    "brightness": 187.71,
    "contrast": 45.35,
    "issues": ["small_image"],
    "warnings": []
  }
}
```

`quality.status` 说明：

| 状态 | 含义 |
|---|---|
| `ok` | 未发现明显质量风险 |
| `warning` | 有方向或比例等提示性风险，但不一定阻断 OCR |
| `review` | 有小图、空白、过暗、低对比度等需要复核的问题 |

常见问题标记：

| 标记 | 含义 |
|---|---|
| `small_image` | 图片尺寸或总像素偏小，可能影响 OCR |
| `landscape_orientation` | 横向页面，需要确认是否符合原始页面方向 |
| `extreme_aspect_ratio` | 长宽比异常，可能是长截图或裁剪异常 |
| `blank_or_nearly_blank_light_page` | 接近白色空白页 |
| `blank_or_nearly_blank_dark_page` | 接近黑色空白页 |
| `too_dark` | 页面过暗 |
| `dark_page` | 页面偏暗 |
| `very_low_contrast` | 对比度极低 |
| `low_contrast` | 对比度偏低 |

验收标准：

- PDF 页数和输出图片数量一致。
- 单张图片输入能生成 1 张标准页面图。
- 图片目录输入能按稳定顺序生成多张标准页面图。
- 单页图片清晰，文字边缘不严重发糊。
- 横向页面能正确记录方向，后续可扩展自动旋转。
- 所有输出页面均为 PNG，且可被后续版面分析模块直接读取。
- `metadata.json` 顶层包含 `quality_summary`。
- 每个页面条目包含 `quality`，能标记小图、空白页、过暗、低对比度和横向页面。

### 6.3 智能版面分析

目标是把页面图片转换成统一、可追溯的 layout JSON。它既要服务普通教材和论文，也要为《中国国家地理》这类复杂杂志页面预留处理能力。

版面分析采用三层设计：

```text
第一层：PP-DocLayout 原始检测
  -> 找出标题、正文、图片、表格、公式、图注等候选区域

第二层：自定义规则修正
  -> 修正 role，判断栏位、阅读顺序、页眉页脚页码和复杂度

第三层：视觉大模型兜底
  -> 只处理复杂页，修正阅读顺序和图文关系
```

#### 6.3.1 第一层：PP-DocLayout 原始检测

输入：

```text
storage/tasks/{task_id}/pages/page_001.png
```

输出：

```text
storage/tasks/{task_id}/layout_raw/page_001.json
```

处理要求：

- 当前实现脚本：`backend/scripts/analyze_layout.py`。
- 运行环境：`conda run -n industrial-cv python backend/scripts/analyze_layout.py {task_id}`。
- 每页独立检测，失败时不影响其他页面继续处理。
- 保留模型原始类型、坐标和置信度。
- 不在第一层删除任何区块。
- 生成调试图 `debug/page_001_layout_overlay.png`，方便人工检查检测框。
- 详细手动验证见 `docs/layout-raw-manual-test.md`。

原始输出示例：

```json
{
  "page_no": 1,
  "image_path": "pages/page_001.png",
  "raw_blocks": [
    {
      "raw_id": "raw_001",
      "raw_type": "title",
      "bbox": [120, 86, 1840, 180],
      "score": 0.93
    }
  ]
}
```

#### 6.3.2 第二层：规则修正

输入：

```text
storage/tasks/{task_id}/layout_raw/page_001.json
```

输出：

```text
storage/tasks/{task_id}/layout/page_001.json
```

规则层负责把模型输出整理成下游可用结构：

- 规则规格以 `docs/layout-rule-spec.md` 为准。
- 当前实现脚本：`backend/scripts/refine_layout.py`。
- 运行环境：`conda run -n industrial-cv python backend/scripts/refine_layout.py {task_id}`。
- 详细手动验证见 `docs/layout-refine-manual-test.md`。
- 坐标统一成 `x1/y1/x2/y2`。
- 原始类型映射为内部 `role`。
- 根据正文块横向分布判断 `single_column`、`double_column`、`multi_column`、`mixed_complex`。
- 给正文、标题、图注、边栏等区块分配 `order`。
- 修正页眉、页脚、页码，并标记 `reading_group: "noise"`。
- 判断页面复杂度，输出 `complexity.need_vlm`。

单栏/双栏判断规则：

- 统计正文块中心点 `center_x`。
- 如果大部分正文块集中在页面中间宽区域，判为单栏。
- 如果正文块明显分布在左右两个 x 区间，判为双栏。
- 如果分布在三个或更多 x 区间，判为多栏或复杂混排。

阅读顺序规则：

- 单栏页面：从上到下，y 坐标接近时按 x 从左到右。
- 双栏论文：跨栏标题/摘要优先，然后左栏从上到下，再右栏从上到下。
- 教材页面：主标题、正文、例题/提示框、图表和图注、脚注。
- 杂志页面：主标题、副标题/导语、主正文栏、图片说明、侧栏；复杂页不强行排序，交给第三层兜底。

复杂度评分建议：

```text
complexity_score =
  图片面积占比
  + 栏位数量
  + unknown 区块比例
  + 区块数量
  + 重叠区块比例
  + 低置信度区块比例
```

复杂度分级：

| level | score | 处理方式 |
|---|---|---|
| `low` | 0.00-0.35 | 不调用大模型 |
| `medium` | 0.35-0.65 | 规则处理，保留低置信度标记 |
| `high` | 0.65-1.00 | 调用视觉大模型 |

#### 6.3.3 第三层：视觉大模型兜底

第三层不作为默认流程，只处理复杂页。

调用条件：

- `complexity.level = high`
- `layout_type = mixed_complex`
- 检测到三栏以上且规则排序置信度低
- 图片面积超过页面 40%，同时存在多个文本块
- 大量 `unknown` 或低置信度区块
- 用户指定对某页精修

输入给大模型的内容：

- 页面图片。
- 第一层检测框结果。
- 第二层规则初判结果。
- 固定 JSON 输出格式要求。

大模型只允许修正：

- `role`
- `order`
- `reading_group`
- `notes`
- `visual_summary`

大模型不允许修改：

- 原始图片。
- 区块坐标。
- 不存在的 `block_id`。

合并策略：

- 大模型置信度足够时，覆盖规则层的 `role/order/reading_group`。
- 大模型置信度低时，只记录建议，不覆盖规则结果。
- 所有大模型修正标记为 `source: "vlm_corrected"`。
- 合并后仍写入统一的 `layout/page_001.json`。

验收标准：

- 普通单栏教材页能按从上到下排序。
- 双栏论文页面能先读左栏，再读右栏。
- 页眉、页脚、页码能被标记为 `noise`。
- 普通图片、表格、图注能被单独标记。
- 中国国家地理这类复杂页面能被识别为 `mixed_complex` 或 `need_vlm = true`。
- 每页生成 `layout_raw`、`layout`，并可选生成检测框调试图。

### 6.4 OCR 文字识别

目标是提取可编辑文本，并保留坐标。

处理策略：

- 当前实现脚本：`backend/scripts/run_ocr.py`。
- 运行环境：`conda run -n industrial-cv python backend/scripts/run_ocr.py {task_id}`。
- 详细手动验证见 `docs/ocr-manual-test.md`。
- 读取 `layout/page_xxx.json`，只对需要文字识别的区块做 OCR。
- 优先 OCR：`title`、`subtitle`、`body`、`caption`、`sidebar`、`note`。
- 默认不把 `header`、`footer`、`page_number`、`adornment` 放入正文 OCR 流程。
- `figure`、`table`、`formula` 第一版可保留占位，后续再做视觉摘要或结构化识别。
- 对 layout block 内部做 OCR，而不是整页无差别 OCR。
- 每条 OCR 结果必须包含：
  - 页码
  - `block_id`
  - `role`
  - `reading_group`
  - 文本
  - 坐标
  - 置信度
  - 所属 layout block
- 低置信度文本不直接丢弃，先保留标记，方便后续人工校对。

验收标准：

- 每页能生成独立 JSON。
- 能从 JSON 追溯到原图坐标。
- 正文识别结果基本按阅读顺序排列。
- OCR 输出中的 `block_id` 能和 layout JSON 对齐。

### 6.5 排版噪音清洗

目标是把 OCR 块转换为可读段落。

当前实现入口：

```bash
conda run -n industrial-cv python backend/scripts/build_document.py {task_id}
```

当前脚本：

- `backend/scripts/build_document.py`

当前输出：

- `backend/storage/tasks/{task_id}/clean/document.json`
- `backend/storage/tasks/{task_id}/clean/book.md`

手动验证文档：

- `docs/document-build-manual-test.md`

第一版采用保守清洗策略：先稳定完成块内断行合并、标题/正文/图注归类、页面结构和章节结构构建；跨页拼段暂不默认开启，避免复杂杂志页面、多栏页面被误合并。

#### 6.5.1 页眉页脚过滤

规则建议：

- 优先使用 layout 中的 `reading_group: "noise"` 过滤页眉、页脚、页码。
- 页面顶部 5%-8% 区域内反复出现的短文本，优先判为页眉。
- 页面底部 5%-8% 区域内的页码、日期、短横线，优先判为页脚或页码。
- 多页重复出现且位置相近的文本，优先判为页眉/页脚。
- 单独的阿拉伯数字、罗马数字、`- 12 -` 这类格式，优先判为页码。

#### 6.5.2 断行合并

规则建议：

- 同一段内连续行的 x 坐标接近、行距稳定，则合并为一个段落。
- 中文正文行尾没有明显标点时，下一行大概率接同一段。
- 行尾是 `。！？；：` 时，下一行如果有首行缩进，通常开启新段。
- 英文单词被连字符断开时，需要合并并移除断词符。
- 只对 `reading_group: "main"` 的正文块默认做连续拼段。
- `caption`、`sidebar`、`note` 不强行拼入主正文，先保留独立段落。

#### 6.5.3 跨页拼段

规则建议：

- 上一页最后一段没有结束标点，下一页第一段不是标题时，尝试拼接。
- 如果下一页第一段有明显首行缩进，不强制拼接。
- 如果上一页末尾是图注、表注、页脚，不拼接。

验收标准：

- 页眉、页脚、页码不会出现在正文中。
- 中文段落不再每行断开。
- 跨页未完段落能自然接上。

### 6.6 标题和章节识别

目标是生成 EPUB 目录。

优先规则：

- layout 标记为 `title` 的文本优先作为标题。
- `subtitle` 可以作为章节标题下的导语或二级标题。
- 字号明显大、居中、短文本，可作为候选标题。
- 符合章节格式的文本优先识别为标题，例如：
  - `第一章`
  - `第1章`
  - `一、`
  - `1.`
  - `1.1`
  - `（一）`

不要过度识别：

- 很短但位于页眉位置的文本不作为标题。
- 图注、表注不要作为章节标题。
- 页码附近的文本不要作为标题。
- `adornment` 和 `sidebar` 默认不作为 EPUB 目录标题。

验收标准：

- 生成的 EPUB 有可用目录。
- Markdown 中标题层级清楚。
- 没有大量误判标题。

### 6.7 Markdown 导出

Markdown 是第一阶段最重要的调试产物。

当前 Markdown 由 `backend/scripts/build_document.py` 同步生成，文件位置为：

```text
backend/storage/tasks/{task_id}/clean/book.md
```

导出格式建议：

```markdown
# 书名或文档标题

## AI 导读

摘要：……

关键词：关键词1、关键词2、关键词3

## 第一章 标题

正文段落……

正文段落……
```

验收标准：

- Markdown 可以直接阅读。
- 标题、段落、摘要和关键词结构清楚。
- 人工修改 Markdown 后，后续能重新生成 EPUB。

### 6.8 EPUB 导出

目标是生成标准电子书文件。

EPUB 内容建议：

- `metadata`：书名、作者、语言、摘要、关键词。
- `nav`：目录。
- `chapter`：按章节拆分 XHTML。
- `style.css`：正文、标题、段落的基础样式。

中文 EPUB 样式建议：

- 正文首行缩进 `2em`。
- 段落行距保持舒适，不要每段之间留过大空白。
- 标题层级清晰，避免全书只有一个章节。
- 默认语言设置为 `zh-CN`。

验收标准：

- EPUB 能被 Calibre 正常打开。
- 能在常见阅读器中显示目录。
- 正文没有明显乱码。
- Markdown 和 EPUB 内容一致。

### 6.9 AI 导读生成

目标是用低成本模型生成辅助阅读信息。

输入：

- 清洗后的全文。
- 如果全文过长，按章节摘要后再汇总。

输出：

- 200 字左右核心摘要。
- 3-5 个关键词。

注意事项：

- AI 摘要只处理清洗后的正文，不处理原始 OCR 噪音。
- 对长文档要分段摘要，避免直接塞完整全文导致成本高、效果差。
- 摘要应作为辅助信息，不替代正文。

验收标准：

- 摘要基本覆盖文档主题。
- 关键词能反映核心内容。
- 摘要和关键词能写入 Markdown 和 EPUB 元数据或导读页。

## 7. API 草案

第一阶段可以只保留 5 个接口。

| 接口 | 方法 | 作用 |
|---|---|---|
| `/api/tasks` | POST | 上传文件并创建转换任务 |
| `/api/tasks/{task_id}` | GET | 查询任务状态、进度和错误 |
| `/api/tasks/{task_id}/start` | POST | 开始转换 |
| `/api/tasks/{task_id}/download/markdown` | GET | 下载 Markdown |
| `/api/tasks/{task_id}/download/epub` | GET | 下载 EPUB |

任务状态返回示例：

```json
{
  "task_id": "20260626_001",
  "status": "ocr_running",
  "progress": 46,
  "message": "正在识别第 12/26 页",
  "downloads": {
    "markdown": null,
    "epub": null
  }
}
```

## 8. 前端最小页面

第一阶段前端只需要一个工作台页面。

页面区域：

- 上传区：拖拽上传或选择文件。
- 文件列表：显示文件名、大小、类型。
- 任务进度：显示当前阶段和百分比。
- 日志区域：显示关键处理步骤。
- 下载区：转换完成后显示 Markdown 和 EPUB 下载按钮。

不建议第一版做太复杂：

- 不需要用户登录。
- 不需要在线编辑器。
- 不需要历史书库。
- 不需要复杂仪表盘。

## 9. 实施顺序

### 第 1 步：跑通文件到页面图片

完成内容：

- 上传 PDF/JPG/PNG。
- 生成任务目录。
- PDF 拆页为图片。
- 图片输入统一保存为页面图片。

验收：

- 任意一个 PDF 能得到对应数量的页面图片。

### 第 2 步：跑通 PP-DocLayout 原始检测

完成内容：

- 调用 PP-DocLayout 或 PaddleOCR 文档版面模型。
- 输出每页 `layout_raw/page_xxx.json`。
- 保存原始类型、坐标、检测置信度。
- 生成 `debug/page_xxx_layout_overlay.png` 调试图。

验收：

- 打开原始 JSON 能看到每页版面检测框。
- 调试图能直观看到标题、正文、图片、表格等候选区域。

### 第 3 步：实现规则修正和阅读顺序

完成内容：

- 把模型原始类型映射为内部 `role`。
- 坐标统一成 `x1/y1/x2/y2`。
- 判断单栏、双栏、多栏、复杂混排。
- 标记页眉、页脚、页码为 `noise`。
- 给正文块、标题、图注、边栏分配 `order` 和 `reading_group`。
- 输出统一的 `layout/page_xxx.json`。

验收：

- 单栏和双栏文档的正文顺序基本正确。
- 复杂杂志页能被标记为 `mixed_complex` 或 `need_vlm = true`。

### 第 4 步：跑通 OCR JSON

完成内容：

- 读取 `layout/page_xxx.json`。
- 只对需要识别的文本区块做 OCR。
- 输出每页 `ocr/page_xxx.json`。
- OCR 结果保留 `block_id`、`role`、`reading_group`、坐标、文本、置信度。

验收：

- 打开 JSON 能看到按 layout block 组织的文字识别结果。
- OCR 结果能追溯回 layout JSON。

### 第 5 步：文本清洗和拼段

完成内容：

- 过滤页眉、页脚、页码。
- 合并断行。
- 跨页拼段。
- 识别标题层级。
- 保留图注、边栏和不确定区块的独立标记。

验收：

- 输出 Markdown 可以顺畅阅读。

### 第 6 步：导出 EPUB

完成内容：

- 根据章节生成 EPUB。
- 写入目录和基础元数据。
- 用 Calibre 检查阅读效果。

验收：

- EPUB 能打开、能跳目录、正文无乱码。

### 第 7 步：接入 AI 导读

完成内容：

- 对清洗后的正文生成摘要和关键词。
- 写入 Markdown 和 EPUB。

验收：

- 导出的 EPUB 首页或元数据中有摘要和关键词。

### 第 8 步：接入复杂页视觉兜底

完成内容：

- 只对 `complexity.need_vlm = true` 的页面调用视觉大模型。
- 请求中携带页面图片、检测框、规则初判结果。
- 大模型返回阅读顺序修正、角色修正、图文摘要。
- 合并结果写回统一 `layout/page_xxx.json`。

验收：

- 中国国家地理复杂页面的主阅读顺序明显改善。
- 大模型失败不影响普通页面流程。
- 大模型修正有 `source` 标记，可追踪。

## 10. 验收样例建议

准备 5 类测试文件：

| 类型 | 用途 |
|---|---|
| 单栏文字版 PDF | 验证基础 OCR、段落合并、EPUB 导出 |
| 双栏论文 PDF | 验证版面分析和阅读顺序 |
| 扫描版图片 PDF | 验证 OCR 稳定性 |
| 多图表教材页 | 验证图文分离和噪音处理边界 |
| 中国国家地理杂志页 | 验证复杂图文混排、多栏、侧栏、图注和复杂页兜底 |

每个样例至少检查：

- 页数是否正确。
- `layout_raw` 是否生成。
- `layout` 是否生成。
- `layout_type` 是否合理。
- `complexity.need_vlm` 是否符合预期。
- OCR 是否漏页。
- 阅读顺序是否错乱。
- 页眉页脚是否被清理。
- Markdown 是否可读。
- EPUB 是否可打开。

## 11. 第一版完成标准

第一版不追求完美排版，重点是形成可用闭环。

达到以下标准即可认为核心功能完成：

- 能上传 PDF/JPG/PNG。
- 能把 PDF 拆成页面图片。
- 能输出 `layout_raw` 原始版面检测结果。
- 能输出统一 `layout` JSON。
- 能判断单栏、双栏、多栏和复杂混排。
- 能标记复杂页是否需要视觉大模型。
- 能输出带坐标的 OCR JSON。
- 能处理单栏和常见双栏阅读顺序。
- 能去掉大部分页眉、页脚、页码。
- 能合并大部分中文断行。
- 能导出 Markdown。
- 能导出 EPUB，并可在 Calibre 中正常阅读。
- 能生成简单摘要和关键词。

## 12. 风险与处理策略

| 风险 | 表现 | 处理策略 |
|---|---|---|
| PDF 版式复杂 | 顺序错乱、标题误判 | 先保证常见单栏/双栏，复杂版式标记 `need_vlm` 或进入人工编辑流程 |
| 杂志图文混排复杂 | 多栏、侧栏、图注和装饰文字混在一起 | 规则层先做复杂度评分，复杂页再调用视觉大模型兜底 |
| 扫描质量差 | OCR 错字多 | 增加图像增强、倾斜校正、低置信度标记 |
| 页眉页脚误删 | 正文内容被删 | 采用多页重复规则，不只靠页面位置 |
| 表格公式难还原 | EPUB 内容断裂 | 第一版保留占位文本，第二版再做表格/公式策略 |
| AI 摘要不准确 | 摘要偏题 | 只基于清洗后正文生成，并保留人工可编辑 Markdown |

## 13. 推荐落地判断

如果目标是尽快做出可用产品，优先顺序应该是：

```text
上传管理 > PDF拆页 > layout_raw > layout规则修正 > OCR JSON > 文本清洗 > Markdown > EPUB > AI导读 > 复杂页视觉兜底
```

其中最关键、最容易决定体验的不是 EPUB 生成，而是：

- layout 坐标是否完整。
- `role` 和 `reading_group` 是否稳定。
- 双栏阅读顺序是否正确。
- 页眉页脚和页码是否清理干净。
- 中文断行是否合并自然。
- 复杂杂志页是否能识别为需要兜底，而不是强行输出错误顺序。

只要这四点做稳，后面的 EPUB、Markdown、AI 导读都比较容易迭代。
