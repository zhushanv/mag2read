# 第一周实操文档：扫描版 PDF OCR 主链路

## 1. 第一周目标

第一周不做完整全栈系统，也不急着做 Word、EPUB。目标是先把 OCR 核心链路跑通：

```text
扫描版 PDF
  ↓
页面渲染为图片
  ↓
OCR 识别文字和坐标
  ↓
生成原始 OCR JSON
  ↓
基础版面整理
  ↓
生成结构化 Document JSON
  ↓
导出 TXT 和 HTML
```

第一周结束时，应能用一个命令处理扫描版 PDF，并得到以下结果：

- 每页 PNG 图片
- 原始 OCR JSON
- 结构化 Document JSON
- 可阅读 TXT 文件
- 可预览 HTML 文件

## 2. 第一周建议目录

先建立最小后端目录，不需要马上搭 React。

```text
backend/
├── scripts/
│   └── run_ocr_demo.py
├── app/
│   └── services/
│       ├── pdf_renderer.py
│       ├── image_preprocessor.py
│       ├── ocr_engine.py
│       ├── layout_analyzer.py
│       ├── document_builder.py
│       └── exporters/
│           ├── txt_exporter.py
│           └── html_exporter.py
├── storage/
│   ├── uploads/
│   ├── pages/
│   ├── ocr/
│   ├── documents/
│   └── outputs/
└── requirements.txt
```

目录职责：

| 目录或文件 | 作用 |
| --- | --- |
| `scripts/run_ocr_demo.py` | 第一周主入口脚本 |
| `pdf_renderer.py` | PDF 页面渲染 |
| `image_preprocessor.py` | 图像预处理 |
| `ocr_engine.py` | OCR 识别 |
| `layout_analyzer.py` | 基础版面分析 |
| `document_builder.py` | 构建结构化文档 |
| `txt_exporter.py` | 导出 TXT |
| `html_exporter.py` | 导出 HTML |
| `storage/pages/` | 保存页面图片 |
| `storage/ocr/` | 保存原始 OCR JSON |
| `storage/documents/` | 保存结构化 Document JSON |
| `storage/outputs/` | 保存导出结果 |

## 3. 环境准备

### 3.1 创建 Conda 虚拟环境

在项目根目录执行：

```bash
conda create -n pdfTrans python=3.10 -y
conda activate pdfTrans
```

如果后续需要在另一台机器复现环境，也可以使用项目根目录中的 `environment.yml`：

```bash
conda env create -f environment.yml
conda activate pdfTrans
```

### 3.2 安装依赖

第一周建议依赖：

```text
pymupdf
paddleocr
paddlepaddle
opencv-python
Pillow
jinja2
```

写入 `backend/requirements.txt`：

```text
pymupdf
paddleocr
paddlepaddle
opencv-python
Pillow
jinja2
```

安装：

```bash
pip install -r backend/requirements.txt
```

说明：

- `PyMuPDF` 用于把 PDF 页面渲染为图片。
- `PaddleOCR` 用于中文 OCR 识别。
- `OpenCV` 用于图像预处理。
- `Jinja2` 用于生成 HTML。

如果 `paddlepaddle` 安装失败，可以先查 PaddlePaddle 官网选择与你系统匹配的安装命令。第一周的核心是跑通流程，不建议在 GPU 配置上花太多时间。

## 4. 第一步：PDF 页面渲染

### 4.1 目标

把扫描版 PDF 的每一页转换为 PNG 图片，为 OCR 做准备。

### 4.2 输入

```text
backend/storage/uploads/sample.pdf
```

### 4.3 输出

```text
backend/storage/pages/{task_id}/page_001.png
backend/storage/pages/{task_id}/page_002.png
...
```

### 4.4 实现要点

在 `pdf_renderer.py` 中实现：

- 打开 PDF 文件。
- 遍历每一页。
- 按 200 或 300 DPI 渲染。
- 保存为 PNG。
- 返回页面图片路径列表。

推荐先用 200 DPI：

- 识别速度较快。
- 图片体积可控。
- 对清晰扫描件通常够用。

后期可以把 DPI 作为参数开放。

### 4.5 验收标准

完成后检查：

- 每一页都生成了图片。
- 图片顺序正确。
- 图片打开后清晰可读。
- 文件名按页码排序，例如 `page_001.png`。

验收命令示例：

```bash
python backend/scripts/run_ocr_demo.py backend/storage/uploads/sample.pdf
```

预期结果：

```text
backend/storage/pages/demo/page_001.png
backend/storage/pages/demo/page_002.png
```

## 5. 第二步：图像预处理

### 5.1 目标

提升 OCR 识别稳定性，尤其是对灰底、低对比度、轻微噪点的扫描件。

### 5.2 输入

```text
backend/storage/pages/{task_id}/page_001.png
```

### 5.3 输出

```text
backend/storage/pages/{task_id}/processed_page_001.png
```

### 5.4 实现要点

在 `image_preprocessor.py` 中实现基础预处理：

- 读取图片。
- 灰度化。
- 轻度降噪。
- 对比度增强或自适应二值化。
- 保存预处理结果。

第一周建议不要过度处理。过强的二值化可能会破坏笔画，反而降低 OCR 准确率。

建议提供一个开关：

```text
enhance_image = true / false
```

当普通 OCR 效果已经不错时，可以直接使用原图。

### 5.5 验收标准

完成后检查：

- 预处理图片没有明显丢字。
- 文字边缘没有被严重破坏。
- 对灰底或偏暗扫描件，文字更清晰。

## 6. 第三步：OCR 文字识别

### 6.1 目标

识别页面图片中的文字，并保留文本框坐标和置信度。

### 6.2 输入

```text
backend/storage/pages/{task_id}/page_001.png
```

或：

```text
backend/storage/pages/{task_id}/processed_page_001.png
```

### 6.3 输出

```text
backend/storage/ocr/{task_id}/ocr_raw.json
```

### 6.4 原始 OCR JSON 格式

建议格式：

```json
{
  "task_id": "demo",
  "pages": [
    {
      "page_no": 1,
      "image_path": "backend/storage/pages/demo/page_001.png",
      "width": 1240,
      "height": 1754,
      "lines": [
        {
          "id": "p1_l1",
          "text": "第一章 绪论",
          "bbox": [120, 80, 600, 130],
          "confidence": 0.98
        }
      ]
    }
  ]
}
```

### 6.5 实现要点

在 `ocr_engine.py` 中实现：

- 初始化 PaddleOCR。
- 对每页图片执行 OCR。
- 提取文字内容。
- 提取文字框坐标。
- 计算矩形边界框 `bbox`。
- 保存置信度。

PaddleOCR 返回的坐标通常是四个点，需要转换为：

```text
[x_min, y_min, x_max, y_max]
```

### 6.6 验收标准

完成后检查：

- 能识别中文。
- 每行文字都有 `text`。
- 每行文字都有 `bbox`。
- 每行文字都有 `confidence`。
- JSON 可以被正常读取。

至少准备 2 份测试文件：

- 清晰单栏扫描 PDF。
- 带图片或双栏的扫描 PDF。

## 7. 第四步：基础版面分析

### 7.1 目标

把 OCR 的“文字行”整理成更接近文档阅读结构的内容块。

OCR 原始结果通常是一行一行的文字。直接导出会出现很多问题：

- 每一行都被拆开。
- 段落不完整。
- 页眉页脚混入正文。
- 双栏页面顺序混乱。

基础版面分析的目标是先解决最影响阅读的问题。

### 7.2 输入

```text
backend/storage/ocr/{task_id}/ocr_raw.json
```

### 7.3 输出

版面分析后的页面块数据，供 `document_builder.py` 使用。

### 7.4 第一周必须实现的规则

#### 按坐标排序

单栏页面先按：

```text
y 从小到大，x 从小到大
```

排序。

#### 段落合并

相邻文字行满足以下条件时，可以合并为同一段：

- x 坐标接近。
- 行间距较小。
- 字体高度接近。
- 当前行不是明显标题。

#### 标题判断

可以用简单规则：

- 文本较短。
- 行高明显大于正文。
- 位于页面上方或段落开始位置。
- 包含“第 X 章”“一、”“1.1”等编号。

#### 页眉页脚标记

第一周先做简单版：

- 页面顶部 8% 区域的短文本标记为 `header_candidate`。
- 页面底部 8% 区域的页码或短文本标记为 `footer_candidate`。

后续再做跨页重复检测。

#### 双栏初步处理

第一周可以做简单规则：

- 如果文本框明显分布在左右两个 x 区域，认为是双栏。
- 先输出左栏内容，再输出右栏内容。

这个规则不需要完美，但要能解释清楚。

### 7.5 验收标准

完成后检查：

- 清晰单栏扫描件能按正常顺序输出。
- 正文不是一行一段。
- 标题能被识别为 `heading`。
- 页码能被标记或过滤。
- 双栏页面不再严重串行。

## 8. 第五步：结构化 Document JSON

### 8.1 目标

把 OCR 和版面分析结果转换成统一中间文档模型。

这是后续导出 DOCX、EPUB、HTML 的基础。

### 8.2 输出

```text
backend/storage/documents/{task_id}/document.json
```

### 8.3 推荐结构

```json
{
  "task_id": "demo",
  "title": "识别出的文档标题",
  "source_type": "scanned_pdf",
  "page_count": 2,
  "quality": {
    "ocr_avg_confidence": 0.94,
    "low_confidence_count": 5
  },
  "pages": [
    {
      "page_no": 1,
      "blocks": [
        {
          "id": "p1_b1",
          "type": "heading",
          "text": "第一章 绪论",
          "bbox": [120, 80, 600, 130],
          "confidence": 0.98
        },
        {
          "id": "p1_b2",
          "type": "paragraph",
          "text": "这里是合并后的正文段落……",
          "bbox": [120, 180, 900, 320],
          "confidence": 0.94
        }
      ]
    }
  ]
}
```

### 8.4 实现要点

在 `document_builder.py` 中实现：

- 读取版面分析结果。
- 生成页面和内容块。
- 计算平均置信度。
- 统计低置信度文字数量。
- 尝试提取文档标题。
- 保存为 JSON。

### 8.5 验收标准

完成后检查：

- JSON 结构清晰。
- 每个 block 都有 `type` 和 `text`。
- 每个 block 保留 `bbox` 和 `confidence`。
- 有基础质量指标。
- 后续导出模块只依赖这个 JSON。

## 9. 第六步：TXT 导出

### 9.1 目标

先验证识别出的文本是否可读。

### 9.2 输入

```text
backend/storage/documents/{task_id}/document.json
```

### 9.3 输出

```text
backend/storage/outputs/{task_id}/result.txt
```

### 9.4 导出规则

- 标题单独成行。
- 段落之间空一行。
- 页与页之间加分页标记。
- 默认不导出页眉页脚。

示例：

```text
第一章 绪论

这里是第一段正文内容……

这里是第二段正文内容……

----- 第 2 页 -----
```

### 9.5 验收标准

完成后检查：

- TXT 能顺畅阅读。
- 段落之间有空行。
- 没有大量无意义换行。
- 页码和页眉页脚没有明显干扰正文。

## 10. 第七步：HTML 导出

### 10.1 目标

用 HTML 做 OCR 结果预览，为后续 React 页面打基础。

### 10.2 输入

```text
backend/storage/documents/{task_id}/document.json
```

### 10.3 输出

```text
backend/storage/outputs/{task_id}/result.html
```

### 10.4 实现要点

在 `html_exporter.py` 中实现：

- 标题输出为 `<h1>`、`<h2>`。
- 段落输出为 `<p>`。
- 每页使用单独的 `<section>`。
- 低置信度内容加样式标记。
- 页面顶部显示 OCR 平均置信度。

低置信度样式示例：

```html
<span class="low-confidence">可能识别错误的文字</span>
```

### 10.5 验收标准

完成后检查：

- 浏览器能打开 HTML。
- 标题和段落层次清楚。
- 页面之间有分隔。
- 低置信度文本有提示。
- 中文显示正常。

## 11. 第八步：主入口脚本

### 11.1 目标

用一个脚本串起第一周全部流程。

### 11.2 脚本路径

```text
backend/scripts/run_ocr_demo.py
```

### 11.3 运行方式

```bash
python backend/scripts/run_ocr_demo.py backend/storage/uploads/sample.pdf
```

### 11.4 脚本流程

```text
1. 接收 PDF 路径
2. 生成 task_id
3. 渲染 PDF 页面为图片
4. 可选图像预处理
5. 执行 OCR
6. 保存 ocr_raw.json
7. 执行基础版面分析
8. 构建 document.json
9. 导出 result.txt
10. 导出 result.html
11. 打印所有输出路径
```

### 11.5 命令行输出建议

```text
任务 ID: demo_20260624_001
PDF 页数: 5
页面图片: backend/storage/pages/demo_20260624_001/
OCR JSON: backend/storage/ocr/demo_20260624_001/ocr_raw.json
Document JSON: backend/storage/documents/demo_20260624_001/document.json
TXT: backend/storage/outputs/demo_20260624_001/result.txt
HTML: backend/storage/outputs/demo_20260624_001/result.html
平均置信度: 0.94
低置信度文本数: 8
```

## 12. 第一周最终验收清单

### 12.1 功能验收

第一周结束时，应完成：

- [ ] 能读取扫描版 PDF。
- [ ] 能把 PDF 每页渲染为 PNG。
- [ ] 能使用 PaddleOCR 识别中文。
- [ ] 能保存原始 OCR JSON。
- [ ] 能保留文字坐标和置信度。
- [ ] 能进行基础排序和段落合并。
- [ ] 能生成结构化 Document JSON。
- [ ] 能导出 TXT。
- [ ] 能导出 HTML。
- [ ] 能统计平均 OCR 置信度。

### 12.2 文件产物验收

运行一次 demo 后，应看到：

```text
backend/storage/pages/{task_id}/page_001.png
backend/storage/ocr/{task_id}/ocr_raw.json
backend/storage/documents/{task_id}/document.json
backend/storage/outputs/{task_id}/result.txt
backend/storage/outputs/{task_id}/result.html
```

### 12.3 效果验收

至少用两份 PDF 测试：

| 测试文件 | 验收重点 |
| --- | --- |
| 清晰单栏扫描 PDF | 文字识别、段落合并、TXT 可读 |
| 双栏或图文混排扫描 PDF | 阅读顺序、标题识别、HTML 预览 |

效果要求：

- 清晰单栏扫描件可读性较好。
- 双栏页面即使不完美，也不应严重左右混排。
- HTML 预览能清楚展示识别结果。
- 低置信度文字能被统计或标记。

## 13. 第一周暂不做的内容

为了避免范围失控，第一周先不做：

- React 前端。
- FastAPI 接口。
- Redis / Celery 异步任务。
- DOCX 导出。
- EPUB 导出。
- 用户登录。
- 在线编辑 OCR 文本框。
- 表格精确还原。
- 复杂杂志像素级排版还原。

这些内容放到第二周以后。第一周的重点是让 OCR 主链路变成稳定、可复用的后端能力。

## 14. 常见问题

### OCR 很慢怎么办？

第一周先限制测试 PDF 页数，例如 3 到 5 页。等主流程稳定后，再加入异步任务和进度条。

### PaddleOCR 安装失败怎么办？

可以先记录问题，并临时用少量图片测试 OCR 环节。不要为了环境问题打乱整体设计。最终展示前再解决 PaddleOCR 环境。

### 识别结果有错别字怎么办？

这是正常情况。第一周先保留置信度和原始文本，为后续“人工校对页面”做准备。

### 段落合并效果不好怎么办？

先保证规则可解释，再逐步调参数。第一周的目标不是完美排版，而是形成可运行的结构化流程。
