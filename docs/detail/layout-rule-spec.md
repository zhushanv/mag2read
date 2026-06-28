# 第二层版面规则规格说明

## 1. 第二层目标

第二层规则引擎接收第一层 `layout_raw/page_xxx.json`，输出下游唯一依赖的统一版面文件：

```text
layout/page_xxx.json
```

第二层不做 OCR，不生成正文文本。它只负责把模型原始检测框整理成可用于 OCR、清洗和 EPUB 导出的结构。

核心目标：

- 把 PP-DocLayout 原始 `raw_type` 映射为内部 `role`。
- 标记每个块是否进入正文阅读流。
- 判断页面版式：单栏、双栏、多栏、图片主导、复杂混排。
- 分配初步阅读顺序 `order`。
- 标记页眉、页脚、页码等噪音。
- 计算复杂度，决定是否需要第三层视觉大模型兜底。

## 2. 输入与输出

### 2.1 输入

```text
backend/storage/tasks/{task_id}/layout_raw/page_001.json
backend/storage/tasks/{task_id}/metadata.json
```

第一层 `raw_blocks[]` 示例：

```json
{
  "raw_id": "p001_raw_0001",
  "raw_type": "text",
  "cls_id": 2,
  "score": 0.9824,
  "bbox": {
    "x1": 124.4275,
    "y1": 746.1649,
    "x2": 909.1643,
    "y2": 883.4792
  }
}
```

### 2.2 输出

```text
backend/storage/tasks/{task_id}/layout/page_001.json
backend/storage/tasks/{task_id}/layout/summary.json
```

统一输出结构：

```json
{
  "task_id": "layout_step1_images",
  "page_no": 1,
  "image_path": "backend/storage/tasks/layout_step1_images/pages/page_001.png",
  "width": 1080,
  "height": 2400,
  "page_type": "magazine_complex",
  "layout_type": "mixed_complex",
  "complexity": {
    "level": "high",
    "score": 0.75,
    "reasons": ["image_area_ratio_gt_0.35", "many_blocks", "has_header_footer"],
    "need_vlm": true
  },
  "blocks": []
}
```

区块结构：

```json
{
  "block_id": "p001_b0001",
  "source": "rule_corrected",
  "raw_id": "p001_raw_0001",
  "raw_type": "text",
  "role": "body",
  "bbox": {
    "x1": 124.4275,
    "y1": 746.1649,
    "x2": 909.1643,
    "y2": 883.4792
  },
  "confidence": {
    "detector": 0.9824,
    "rule": 0.85,
    "final": 0.9162
  },
  "column": 1,
  "order": 3,
  "reading_group": "main",
  "is_noise": false,
  "notes": []
}
```

## 3. 第一版内部枚举

### 3.1 role

| role | 含义 | 是否默认 OCR |
|---|---|---|
| `title` | 主标题、文档标题、章节标题 | 是 |
| `subtitle` | 副标题、小标题 | 是 |
| `body` | 正文 | 是 |
| `caption` | 图注、表注、图片说明 | 是 |
| `figure` | 图片、照片、地图、图形 | 否 |
| `table` | 表格区域 | 否 |
| `formula` | 公式、手写公式候选 | 否 |
| `header` | 页眉、顶部状态栏 | 否 |
| `footer` | 页脚、底部导航或页脚信息 | 否 |
| `page_number` | 页码 | 否 |
| `sidebar` | 边栏、补充说明 | 是 |
| `adornment` | 装饰文字、按钮、非正文 UI 文案 | 否 |
| `unknown` | 不确定区域 | 视情况 |

### 3.2 reading_group

| reading_group | 含义 |
|---|---|
| `main` | 主阅读流 |
| `caption` | 图注、表注 |
| `sidebar` | 边栏、补充阅读 |
| `note` | 脚注、注释 |
| `visual` | 图片、表格、公式等视觉块 |
| `noise` | 页眉、页脚、页码、装饰性内容 |
| `unknown` | 暂不确定 |

### 3.3 layout_type

| layout_type | 含义 |
|---|---|
| `single_column` | 单栏 |
| `double_column` | 双栏 |
| `multi_column` | 三栏及以上 |
| `image_dominant` | 图片主导 |
| `mixed_complex` | 复杂图文混排 |
| `unknown` | 不确定 |

### 3.4 page_type

| page_type | 含义 |
|---|---|
| `book_text` | 普通书籍、教材正文页 |
| `paper` | 论文或报告页 |
| `magazine_simple` | 简单图文页 |
| `magazine_complex` | 复杂杂志页、公众号长截图 |
| `form_or_resume` | 表格、简历、表单类页面 |
| `handwriting` | 手写笔记页 |
| `unknown` | 不确定 |

## 4. raw_type 到 role 的基础映射

基于当前 PP-DocLayout 实际输出，第一版先覆盖以下类型。

| raw_type | 默认 role | 默认 reading_group | 说明 |
|---|---|---|---|
| `doc_title` | `title` | `main` | 文档标题，优先级最高 |
| `title` | `title` | `main` | 兼容可能出现的标题标签 |
| `paragraph_title` | `subtitle` | `main` | 小标题，后续可按位置升级为 `title` |
| `figure_title` | `caption` | `caption` | 图题、图注 |
| `table_title` | `caption` | `caption` | 表题、表注 |
| `text` | `body` | `main` | 正文候选 |
| `plain text` | `body` | `main` | 兼容标签 |
| `image` | `figure` | `visual` | 图片、图形、装饰图 |
| `figure` | `figure` | `visual` | 兼容标签 |
| `table` | `table` | `visual` | 表格 |
| `formula` | `formula` | `visual` | 公式或被模型误判的手写区域 |
| `header` | `header` | `noise` | 页眉、手机状态栏、顶部 UI |
| `footer` | `footer` | `noise` | 页脚、底部 UI |
| `reference` | `body` | `main` | 参考文献区域，暂按正文 |
| 其他 | `unknown` | `unknown` | 保留，后续规则修正 |

## 5. 坐标派生字段

第二层内部需要为每个块计算以下派生值：

```text
width = x2 - x1
height = y2 - y1
area = width * height
area_ratio = area / page_area
center_x = (x1 + x2) / 2
center_y = (y1 + y2) / 2
top_ratio = y1 / page_height
bottom_ratio = y2 / page_height
left_ratio = x1 / page_width
right_ratio = x2 / page_width
```

这些字段可用于规则判断，不一定全部写入最终 JSON。

## 6. 噪音修正规则

### 6.1 页眉

满足以下条件之一，可修正为 `header`：

- `raw_type = header`。
- `top_ratio <= 0.08`，且块高度小于页面高度 5%。
- 多页重复出现且位置接近的短文本块。第一版未接 OCR，可先保留为后续规则。

限制：

- 如果块面积很大，或者宽度超过页面 60%，且 `raw_type` 是 `doc_title`，不要仅因靠上改成页眉。
- 杂志/公众号顶部导航、手机状态栏可先标为 `header` 和 `noise`。

### 6.2 页脚

满足以下条件之一，可修正为 `footer`：

- `raw_type = footer`。
- `bottom_ratio >= 0.94`，且块高度小于页面高度 5%。

限制：

- 大块表格、图注、正文即使靠近底部，也不要直接改成 `footer`。

### 6.3 页码

当前第一版没有 OCR 文本，页码只做弱判断：

- 位于页面底部 8% 区域。
- 框较小。
- `raw_type` 为 `text` 或 `footer`。

由于缺少文本内容，第一版默认标为 `footer`，不强行标为 `page_number`。等 OCR 后可根据文本正则修正。

## 7. 标题修正规则

### 7.1 升级为 title

满足以下条件之一，`subtitle` 可升级为 `title`：

- `raw_type = doc_title`。
- 位于页面上半部分，宽度超过页面 35%，高度明显大于正文块中位高度。
- 页面中没有 `doc_title`，且该块是靠前的 `paragraph_title`。

### 7.2 保持 subtitle

以下情况保持 `subtitle`：

- `raw_type = paragraph_title`。
- 块较短，靠近正文区域。
- 不在页眉/页脚区域。

### 7.3 降级为 adornment

以下情况可从 `subtitle/title` 降级为 `adornment`：

- 位于页面底部按钮区域。
- 靠近大面积背景按钮或 UI 元素。
- 宽高较小，且不在主正文阅读流附近。

第一版没有 OCR 文本和颜色分析，先只对明显底部 UI 区域做弱处理。

## 8. 图注和表注规则

### 8.1 figure_title

`raw_type = figure_title` 默认：

```text
role = caption
reading_group = caption
```

如果它靠近最近的 `figure` 或 `table`，后续可建立 `related_block_id`。第一版先不强制建立关联。

### 8.2 靠近视觉块的短文本

满足以下条件的 `text` 可候选为 `caption`：

- 高度小于正文块中位高度的 1.2 倍。
- 距离最近 `figure/table` 的垂直距离小于页面高度 3%。
- 不在页眉页脚区域。

第一版先保守处理：只把 `figure_title/table_title` 映射为 `caption`，避免误伤正文。

## 9. 手写笔记和 formula 规则

当前样例中，`handwrite.jpg` 的手写内容大量被 PP-DocLayout 标为 `formula`。

第一版规则：

- 如果页面中 `formula` 数量占全部块的 50% 以上，且几乎没有 `table/image/doc_title`，页面判定为 `handwriting`。
- 在 `handwriting` 页面中，`formula` 不再作为纯视觉公式处理，而是改为：

```text
role = body
reading_group = main
notes += ["formula_reclassified_as_handwriting_body"]
```

原因：手写笔记需要进入 OCR 或后续手写识别，而不是被当作公式占位跳过。

非手写页面中的 `formula` 仍保持：

```text
role = formula
reading_group = visual
```

## 10. 表格/简历/表单规则

满足以下条件之一，页面可判定为 `form_or_resume`：

- 存在 `table`。
- 大面积 `table` 或多个规则矩形区域。
- `table` 面积占页面面积超过 15%。

第一版：

- `table` 保持 `role = table`。
- 表格页的文本块仍保留，但排序时表格作为视觉块参与。
- 表格结构化留到后续模块处理。

## 11. 栏位判断规则

只使用以下候选块判断栏位：

```text
role in ["body", "subtitle", "caption"]
reading_group != "noise"
area_ratio < 0.35
```

排除：

- `figure`
- `table`
- `formula`
- `header`
- `footer`
- `adornment`
- 大面积跨栏标题

### 11.1 单栏

满足：

- 有效文本块数量较少，或
- 文本块 `center_x` 主要集中在一个横向区间。

输出：

```text
layout_type = single_column
column = 1
```

### 11.2 双栏

满足：

- 文本块 `center_x` 明显分布在左右两个区间。
- 左右区间之间有明显间隔。
- 每个区间至少有 2 个文本块。

输出：

```text
layout_type = double_column
左栏 column = 1
右栏 column = 2
```

### 11.3 多栏或复杂混排

满足：

- `center_x` 分布在 3 个及以上区间。
- 图片/表格穿插导致文本块无法稳定分栏。
- 页面内视觉块面积较大且文本块分散。

输出：

```text
layout_type = multi_column 或 mixed_complex
```

第一版实现建议：

- 对普通教材/论文先支持单栏、双栏。
- 对复杂页面保守标记为 `mixed_complex`，不强行给出完美顺序。

## 12. 阅读顺序规则

### 12.1 通用优先级

先排除：

```text
reading_group = noise
```

排序组优先级：

```text
title/subtitle 跨栏块
main 正文块
caption 图注/表注
visual 视觉块
sidebar/note
unknown
```

### 12.2 单栏排序

规则：

```text
按 y1 从上到下
y1 接近时按 x1 从左到右
```

### 12.3 双栏排序

规则：

```text
跨栏标题先读
左栏从上到下
右栏从上到下
图表/图注按其 y 坐标插入附近
```

跨栏判断：

```text
block_width / page_width >= 0.55
```

### 12.4 复杂混排排序

复杂页不追求最终正确顺序。

第一版：

- 仍按视觉顺序给出 `order`。
- 标记 `complexity.need_vlm = true`。
- 后续第三层再修正阅读顺序。

## 13. 页面类型判断

按优先级判断：

### 13.1 handwriting

```text
formula_count / total_blocks >= 0.5
and table_count == 0
and image_count <= 1
```

### 13.2 form_or_resume

```text
table_count >= 1
or table_area_ratio >= 0.15
```

### 13.3 magazine_complex

```text
image_area_ratio >= 0.25
and text_block_count >= 6
```

或：

```text
layout_type in ["multi_column", "mixed_complex"]
and visual_block_count >= 2
```

### 13.4 paper

```text
layout_type = double_column
and text_block_count >= 6
and image_area_ratio < 0.35
```

### 13.5 book_text

```text
layout_type = single_column
and body_count >= 2
and image_area_ratio < 0.25
```

否则：

```text
unknown
```

## 14. 复杂度评分规则

复杂度用于决定是否调用第三层视觉大模型。

第一版按规则加分，最高截断为 1.0：

| 条件 | 加分 | reason |
|---|---:|---|
| 图片/视觉块面积占比 >= 0.25 | 0.20 | `visual_area_ratio_gt_0.25` |
| 图片/视觉块面积占比 >= 0.40 | 0.30 | `visual_area_ratio_gt_0.40` |
| 文本块数量 >= 20 | 0.15 | `many_text_blocks` |
| 总块数 >= 30 | 0.15 | `many_blocks` |
| layout_type 为 `multi_column` | 0.20 | `multi_column` |
| layout_type 为 `mixed_complex` | 0.30 | `mixed_complex` |
| unknown 块比例 >= 0.20 | 0.15 | `many_unknown_blocks` |
| 低置信度块比例 >= 0.25 | 0.10 | `many_low_confidence_blocks` |
| 同时有 header 和 footer | 0.05 | `has_header_footer` |
| 表格页 | 0.10 | `has_table` |
| 手写页 | 0.15 | `handwriting_page` |

分级：

| 分数 | level | need_vlm |
|---|---|---|
| 0.00-0.34 | `low` | false |
| 0.35-0.64 | `medium` | false |
| 0.65-1.00 | `high` | true |

强制 `need_vlm = true` 条件：

- `page_type = magazine_complex` 且 `complexity.score >= 0.5`。
- `layout_type = mixed_complex`。
- `unknown` 块比例超过 30%。

## 15. 置信度规则

输出字段：

```json
"confidence": {
  "detector": 0.91,
  "rule": 0.85,
  "final": 0.88
}
```

第一版计算：

```text
detector = raw score
rule = 根据规则来源给固定值
final = (detector + rule) / 2
```

规则置信度建议：

| 情况 | rule |
|---|---:|
| raw_type 直接映射，无修正 | 0.85 |
| header/footer 坐标修正 | 0.80 |
| handwriting formula 重分类 | 0.75 |
| title/subtitle 升降级 | 0.70 |
| unknown | 0.40 |

## 16. 第一版实现边界

第一版做：

- `raw_type -> role` 映射。
- `reading_group` 标记。
- `header/footer` 坐标修正。
- 手写页 `formula -> body` 重分类。
- 单栏/双栏/复杂混排判断。
- 初步 `order`。
- `complexity` 和 `need_vlm`。
- 输出 `layout/page_xxx.json` 和 `layout/summary.json`。

第一版不做：

- 不做 OCR 文本正则判断页码。
- 不做图文语义关联。
- 不做表格结构还原。
- 不做视觉大模型调用。
- 不保证复杂杂志页最终阅读顺序完全正确。

## 17. 当前样例预期

### 17.1 complexLayout.jpg

预期：

- `page_type = magazine_complex`
- `layout_type = mixed_complex`
- `image` -> `figure`
- `header/footer` -> `noise`
- 大量 `text` -> `body`
- `paragraph_title` -> `subtitle`
- `need_vlm` 大概率为 true

### 17.2 handwrite.jpg

预期：

- `page_type = handwriting`
- 大量 `formula` 重分类为 `body`
- `reading_group = main`
- `need_vlm` 可为 false 或 medium，后续进入手写 OCR 策略

### 17.3 poet.jpg

预期：

- `page_type = book_text` 或 `magazine_simple`
- `layout_type = single_column`
- `text` -> `body`
- `image` -> `figure`

### 17.4 table.jpg

预期：

- `page_type = form_or_resume`
- `table` -> `table`
- `doc_title` -> `title`
- `need_vlm` 视复杂度而定

### 17.5 pdf1.0.pdf

预期：

- 多数页面为 `book_text`、`paper` 或 `magazine_simple`
- `footer` 标记为 `noise`
- `doc_title`、`paragraph_title` 分别映射为 `title`、`subtitle`
- 暗页质量 warning 不影响 layout 规则
