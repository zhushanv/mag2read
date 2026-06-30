# 阅读稿人工编辑与最终稿导出分阶段实现文档

## 1. 背景

当前系统已经可以完成：

- 上传 PDF 或图片。
- 渲染页面图片。
- 执行本地 OCR 或百度云端 OCR。
- 生成 `clean/document.json`。
- 在任务详情页展示阅读稿预览。
- 对图片、表格、公式等图形块生成 `media/*.png`，并在阅读预览中展示。

但从产品使用流程看，`clean/document.json` 仍然只是“系统初稿”，不能直接等同于最终交付文档。用户真正需要的是：

```text
系统识别初稿
  ↓
用户人工检查和修改
  ↓
形成最终阅读稿
  ↓
按最终稿导出 DOCX / Markdown / HTML / PDF 等文件
```

因此后续开发不应优先围绕 `clean/document.json` 做导出增强，而应先补齐“人工编辑稿”的数据层和交互层，再让导出模块读取人工编辑后的最终稿。

## 2. 总体目标

本阶段目标分三步完成：

1. 支持右侧阅读稿人工编辑，并保存为最终稿数据。
2. 导出文件优先使用人工编辑后的最终稿，且保留图片、表格、公式等媒体内容。
3. 在左侧原文预览和右侧阅读稿之间建立 block 级联动。

整体数据流建议调整为：

```text
layout/page_*.json
ocr/page_*.json
media/*.png
        ↓
clean/document.json          # 系统生成稿
        ↓
edited/document.json         # 人工最终稿
        ↓
exports/*                    # 最终导出文件
```

其中：

- `clean/document.json` 保留为系统生成结果，方便回溯和重新生成。
- `edited/document.json` 作为人工修改后的最终稿。
- 导出模块优先读取 `edited/document.json`，没有编辑稿时再回退读取 `clean/document.json`。

## 3. 设计原则

### 3.1 不直接覆盖 clean/document.json

不建议把用户修改直接写回 `clean/document.json`。原因是：

- `clean/document.json` 是系统流水线产物，后续重跑 OCR 或清洗时可能被覆盖。
- 人工修改结果需要保留版本边界，方便比较“机器初稿”和“人工最终稿”。
- 出问题时可以快速回退到初始清洗结果。

建议新增：

```text
backend/storage/tasks/{task_id}/edited/document.json
backend/storage/tasks/{task_id}/edited/history.json
```

第一版可以只做 `document.json`，后续再补 `history.json`。

### 3.2 第一版只做块级编辑

不建议第一版直接做完整富文本编辑器。更稳妥的方式是“块级编辑”：

- 一个标题是一个 block。
- 一个自然段是一个 block。
- 一个图片、表格或公式也是一个 block。
- 用户可以修改文本内容和图片说明。
- 暂时不支持复杂拖拽、自由排版、跨块富文本格式。

这样可以最大程度复用已有的 `block_id`、`source_block_ids`、`media_path` 和 `bbox`。

### 3.3 导出只认最终稿

导出模块的输入规则应统一为：

```text
如果存在 edited/document.json：
    使用 edited/document.json
否则：
    使用 clean/document.json
```

这样用户在右侧阅读稿中的修改才会真实反映到导出文件中。

## 4. 分阶段实施计划

## 4.1 第一阶段：人工编辑稿数据层

### 目标

建立人工最终稿的数据保存能力。此阶段可以先不做复杂 UI，只要后端能读取、保存、返回编辑稿即可。

### 后端新增能力

建议新增接口：

```text
GET /api/tasks/{task_id}/edited-document
PUT /api/tasks/{task_id}/edited-document
POST /api/tasks/{task_id}/edited-document/reset
```

接口职责：

- `GET`：优先返回 `edited/document.json`，不存在时返回 `clean/document.json`，并标识当前是否已经人工编辑。
- `PUT`：保存前端提交的人工最终稿。
- `reset`：删除或弃用人工编辑稿，恢复到系统清洗稿。

### edited/document.json 建议结构

第一版尽量沿用 `clean/document.json`，减少适配成本：

```json
{
  "task_id": "demo_task",
  "version": 1,
  "source": "manual_edit",
  "base_document_path": "backend/storage/tasks/demo_task/clean/document.json",
  "edited_at": "2026-06-30T16:00:00",
  "pages": [
    {
      "page_no": 1,
      "blocks": [
        {
          "id": "c00001",
          "block_id": "edited_c00001",
          "source_block_ids": ["p001_b0001"],
          "type": "paragraph",
          "role": "body",
          "text": "人工修改后的正文。",
          "source_pages": [1],
          "bbox": {
            "x1": 10,
            "y1": 20,
            "x2": 300,
            "y2": 80
          },
          "media_path": null,
          "is_graphical": false
        }
      ]
    }
  ]
}
```

图形块建议保留：

```json
{
  "id": "c00012",
  "block_id": "edited_c00012",
  "source_block_ids": ["p001_b0008"],
  "type": "figure",
  "role": "figure",
  "text": "用户补充的图片说明。",
  "media_path": "backend/storage/tasks/demo_task/media/page_001_p001_b0008_figure.png",
  "media_width": 890,
  "media_height": 640,
  "is_graphical": true
}
```

### 第一阶段验收标准

- 新任务完成后可以读取系统生成稿。
- 用户保存后，任务目录出现 `edited/document.json`。
- 再次打开任务详情页时，优先读取人工编辑稿。
- 重置后可以恢复显示系统清洗稿。

### 第一阶段落地说明

本阶段实际实现范围：

- 新增编辑稿文件管理模块：

```text
backend/app/modules/edited_document.py
```

- 新增后端接口：

```text
GET /api/tasks/{task_id}/edited-document
PUT /api/tasks/{task_id}/edited-document
POST /api/tasks/{task_id}/edited-document/reset
```

- `GET` 接口会优先返回 `edited/document.json`，不存在时返回 `clean/document.json`。
- `PUT` 接口会把提交的文档保存为 `edited/document.json`，并写入 `manual_edit` 元数据。
- `reset` 接口会移除 `edited/document.json`，重新回到系统清洗稿。
- 任务详情页的阅读稿预览已经改为读取 `/edited-document`，因此后续人工编辑保存后，刷新页面会优先显示人工稿。

第一阶段暂未实现：

- 右侧可视化编辑器。
- 保存按钮和重置按钮。
- 导出读取 `edited/document.json`。
- 编辑历史版本。

这些内容进入后续阶段。

## 4.2 第二阶段：右侧阅读稿块级编辑 UI

### 目标

让右侧阅读稿从“只读预览”变成“可编辑最终稿”。

### 推荐交互

右侧阅读稿区域增加编辑状态：

```text
查看模式
  ↓ 点击“编辑”
编辑模式
  ↓ 修改文本 / 图片说明
  ↓ 点击“保存”
保存为 edited/document.json
```

每个 block 的处理方式：

| block 类型 | 第一版编辑能力 |
| --- | --- |
| title / subtitle | 可修改文字 |
| body / paragraph | 可修改文字 |
| caption / note | 可修改文字 |
| figure / image | 保留图片，可修改说明文字 |
| table | 第一版可保留图片或 markdown 文本，不做复杂表格编辑 |
| formula | 保留图片，可修改说明文字 |

### 保存策略

前端不建议每输入一个字就保存。第一版建议：

- 用户点击“保存”时整体提交。
- 页面离开或刷新前，如果存在未保存修改，提示用户保存。
- 保存成功后更新本地状态。

后续可以升级为自动保存：

```text
输入停止 800ms 后自动保存草稿
```

但第一版不建议引入自动保存，避免状态复杂。

### 第一版不建议做的内容

以下能力可以后置：

- 拖拽调整段落顺序。
- 合并多个段落。
- 拆分段落。
- 富文本样式，如加粗、字体、颜色。
- 表格单元格级编辑。
- 多人协同编辑。

这些功能都会明显增加状态管理和导出复杂度。

### 第二阶段验收标准

- 用户可以修改右侧阅读稿文字。
- 用户可以修改图片/表格/公式说明文字。
- 保存后刷新页面，修改仍然存在。
- 重置后回到系统清洗稿。
- 未保存修改有明确提示。

### 第二阶段落地说明

本阶段实际实现范围：

- 任务详情页右侧阅读稿支持进入编辑模式。
- 标题、正文、图注等文本块可以直接编辑。
- 图片、表格、公式等媒体块在编辑模式下会自动显示，并允许修改说明文字。
- 点击“保存”后，前端通过 `PUT /api/tasks/{task_id}/edited-document` 保存为人工稿。
- 点击“重置”后，前端通过 `POST /api/tasks/{task_id}/edited-document/reset` 恢复系统清洗稿。
- 页面刷新或重新进入任务详情时，会继续优先展示人工稿。
- 存在未保存修改时，页面会显示提示；用户刷新或关闭页面前也会触发浏览器确认。
- 退出编辑模式时，如果存在未保存修改，会先询问是否放弃本次修改。

第二阶段暂未实现：

- 段落删除、合并、拆分。
- 拖拽调整块顺序。
- 富文本样式编辑。
- 自动保存和编辑历史列表。
- 左右原文区域联动。

## 4.3 第三阶段：最终稿导出

### 目标

导出文件以人工最终稿为准，并支持媒体内容嵌入。

### 导出输入选择

新增统一读取函数，例如：

```text
load_export_document(task_dir)
```

逻辑：

```text
if edited/document.json exists:
    return edited/document.json
else:
    return clean/document.json
```

后续所有导出格式都从这个函数取数据，避免各模块各自判断。

### DOCX 导出规则

DOCX 导出应支持：

- 标题块导出为标题样式。
- 正文块导出为普通段落。
- 图片块根据 `media_path` 嵌入图片。
- 图片说明文字可以放在图片下方。
- 表格块如果有结构化 markdown，可先按文本导出；如果有 `media_path`，优先按图片导出。
- 公式块第一版按图片导出。

图片尺寸建议：

```text
最大宽度不超过正文区域宽度
保持原图比例
过小图片不强行放大
```

缺失图片时降级输出：

```text
[图片缺失：page_001_xxx.png]
```

这样导出不会因为单张图片缺失而整体失败。

### Markdown / HTML 导出规则

Markdown 可输出相对路径：

```md
![图片说明](../media/page_001_p001_b0008_figure.png)
```

HTML 可输出：

```html
<figure>
  <img src="../media/page_001_p001_b0008_figure.png" alt="图片说明">
  <figcaption>图片说明</figcaption>
</figure>
```

如果后续导出为一个可分发压缩包，需要把 `media/` 一起复制到输出目录。

### 第三阶段验收标准

- 用户修改后的文字进入 DOCX。
- 阅读稿中显示的图片进入 DOCX。
- 图片说明文字进入 DOCX。
- 没有人工编辑稿时，仍然可以从 `clean/document.json` 正常导出。
- 缺失图片不会导致导出失败。

## 4.4 第四阶段：左右预览联动

### 目标

实现左侧原文区域和右侧编辑稿 block 的互相定位。

第一版建议做 block 级联动，而不是字符级或行级联动。

### 核心映射

右侧编辑稿 block 保留：

```json
{
  "block_id": "edited_c00012",
  "source_block_ids": ["p001_b0008"],
  "source_pages": [1]
}
```

左侧原文预览使用 `layout/page_*.json` 中的：

```json
{
  "block_id": "p001_b0008",
  "bbox": {
    "x1": 26,
    "y1": 546,
    "x2": 342,
    "y2": 772
  }
}
```

联动关系：

```text
右侧 edited block
  ↓ source_block_ids
左侧 layout block
  ↓ bbox
页面图上画高亮框
```

### 交互方式

左侧点击：

```text
点击页面图上的某个 bbox overlay
  ↓
获得 source_block_id
  ↓
找到右侧包含该 source_block_id 的 edited block
  ↓
右侧滚动到该 block 并高亮
```

右侧点击：

```text
点击某个编辑 block
  ↓
读取 source_block_ids 和 source_pages
  ↓
左侧滚动到对应页面
  ↓
页面图上高亮对应 bbox
```

### 坐标缩放

左侧页面图通常会缩放显示，因此 bbox 不能直接用原始坐标。需要计算：

```text
scale_x = displayed_image_width / layout_width
scale_y = displayed_image_height / layout_height
```

overlay 坐标：

```text
left = bbox.x1 * scale_x
top = bbox.y1 * scale_y
width = (bbox.x2 - bbox.x1) * scale_x
height = (bbox.y2 - bbox.y1) * scale_y
```

如果页面图大小变化，需要重新计算 overlay。

### 第四阶段验收标准

- 点击左侧原文区域，右侧对应 block 高亮并滚动到可见区域。
- 点击右侧编辑 block，左侧对应页面和区域高亮。
- 多页 PDF 可以正确滚动到对应页。
- 图形块和文本块都能联动。
- 如果一个编辑 block 对应多个原始 block，可以同时高亮多个区域。

## 5. 关键风险与处理方式

### 5.1 人工编辑稿和系统初稿不同步

如果用户已经编辑过，但后来重新跑 OCR 或清洗，`edited/document.json` 可能基于旧的 `clean/document.json`。

建议在 `edited/document.json` 里保存：

```json
{
  "base_document_hash": "xxx",
  "base_updated_at": "2026-06-30T16:00:00"
}
```

打开任务时检查 hash。如果系统初稿变化，提示用户：

```text
系统识别结果已更新，当前人工编辑稿可能不是基于最新识别结果。
```

第一版可以先记录，不强制处理。

### 5.2 一个编辑 block 对应多个原始 block

后续如果支持合并段落，就会出现：

```json
"source_block_ids": ["p001_b0003", "p001_b0004"]
```

因此从第一版开始就建议使用数组，不要只保存一个 `source_block_id`。

### 5.3 图片路径失效

如果 `media_path` 对应文件不存在，前端和导出都要降级：

- 前端显示“媒体素材未生成”。
- DOCX 输出占位文本。
- Markdown/HTML 可以输出占位说明。

不要让单张图片导致整个导出失败。

### 5.4 过早引入富文本编辑器

富文本编辑器会带来：

- HTML 与结构化 JSON 的转换问题。
- 图片、表格、公式混排问题。
- 导出 DOCX 样式映射问题。
- 撤销、粘贴、快捷键等额外复杂度。

因此第一版应坚持 block 级编辑。等最终稿保存和导出稳定后，再评估是否引入 TipTap、Slate 或 ProseMirror 这类编辑器。

## 6. 推荐开发顺序

建议按下面顺序开发：

```text
1. 后端 edited/document.json 读写接口
2. 前端右侧阅读稿编辑模式
3. 保存、重置、未保存提示
4. 导出模块读取 edited 优先
5. DOCX 插入 media 图片
6. Markdown/HTML 输出 media 引用
7. 左右 block 级联动
8. 后续增强：段落删除、合并、移动、表格编辑
```

其中 1 到 4 是核心闭环。完成后，用户已经可以：

```text
查看识别结果 → 修改最终稿 → 保存 → 导出修改后的文件
```

图片导出和左右联动可以在这个闭环稳定后继续增强。

## 7. 第一版最小可用范围

为了避免一次性做得过大，第一版建议只承诺以下能力：

- 右侧阅读稿文本可编辑。
- 图片、表格、公式块保留，并允许修改说明文字。
- 保存人工最终稿。
- 重置人工最终稿。
- 导出时优先使用人工最终稿。
- DOCX 中包含最终稿文字和图片。

暂不承诺：

- 表格单元格编辑。
- 富文本样式编辑。
- 段落拖拽排序。
- 多人协同。
- 自动保存历史版本。
- 字符级左右定位。

## 8. 手动测试建议

### 8.1 人工编辑保存

1. 上传一个包含正文和图片的 PDF。
2. 等待任务处理完成。
3. 打开任务详情页。
4. 进入阅读稿编辑模式。
5. 修改一个标题、一个正文段落、一个图片说明。
6. 点击保存。
7. 刷新页面。
8. 检查修改内容仍然存在。
9. 检查任务目录是否生成：

```text
backend/storage/tasks/{task_id}/edited/document.json
```

### 8.2 重置编辑稿

1. 在已有编辑稿的任务中点击重置。
2. 确认右侧阅读稿恢复为系统清洗稿。
3. 检查再次刷新页面后仍然显示系统清洗稿。

### 8.3 最终稿导出

1. 修改右侧阅读稿内容并保存。
2. 导出 DOCX。
3. 打开 DOCX。
4. 检查标题、正文是否为人工修改后的内容。
5. 检查图片是否出现在文档中。
6. 检查图片说明是否为人工修改后的内容。

### 8.4 左右联动

1. 打开多页 PDF 任务。
2. 点击右侧某个正文 block。
3. 检查左侧是否滚动到对应页面并高亮原文区域。
4. 点击左侧某个图片区域。
5. 检查右侧是否滚动到对应图片 block 并高亮。

## 9. 结论

后续开发应先完成“人工编辑稿”闭环，再做导出增强。原因是导出的真实目标不是系统初稿，而是用户确认后的最终稿。

推荐优先完成：

```text
edited/document.json 数据层
  ↓
右侧 block 级编辑
  ↓
导出读取 edited 优先
  ↓
DOCX 嵌入 media 图片
  ↓
左右 block 级联动
```

这样可以保证每一步都有独立价值，也能避免先做导出后又因为人工编辑数据源改变而返工。
