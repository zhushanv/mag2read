# OCR 核心方案

## 1. 核心定位

本项目的核心功能是对扫描版 PDF 进行 OCR 识别，并将识别结果重建为可编辑、可阅读、可导出的结构化文档。

扫描版 PDF 的主要问题是：

- 页面内容本质上是图片。
- 无法直接复制文字。
- 缺少段落、标题、表格等语义信息。
- 多栏排版和图文混排会影响阅读顺序。

因此系统不能只调用一次 OCR，而应形成完整流水线：

```text
PDF 页面渲染
  ↓
图像预处理
  ↓
OCR 文字检测与识别
  ↓
版面区域分析
  ↓
阅读顺序恢复
  ↓
文档结构重建
  ↓
多格式导出
```

## 2. PDF 页面渲染

使用 PyMuPDF 将 PDF 每一页渲染为高分辨率图片。

推荐参数：

- DPI：200 到 300
- 格式：PNG
- 色彩：RGB 或灰度

较高 DPI 有助于提升 OCR 准确率，但会增加处理时间。课程项目中可以默认 200 DPI，并提供高级选项。

## 3. 图像预处理

图像预处理使用 OpenCV，目的是提高 OCR 的稳定性。

基础处理：

- 灰度化
- 自适应二值化
- 降噪
- 对比度增强
- 倾斜校正

可选处理：

- 边缘增强
- 去除背景纹理
- 页面裁边
- 去除扫描黑边

建议实现策略：

- 默认使用轻量预处理，避免破坏原始文字。
- 对低质量扫描件提供“增强识别模式”。

## 4. OCR 引擎选择

首选 PaddleOCR。

原因：

- 中文识别效果较好。
- 支持文字检测和文字识别。
- 能返回文本框坐标和置信度。
- PP-Structure 可用于表格和版面结构识别。

建议配置：

- `lang="ch"`：中文和英文混合识别。
- 开启方向分类器，用于处理旋转文字。
- 保存每个文本框的坐标、文字和置信度。

## 5. OCR 结果结构

单页 OCR 结果建议统一成如下结构：

```json
{
  "page_no": 1,
  "image_path": "storage/pages/task_001/page_001.png",
  "lines": [
    {
      "text": "基于 Python 的 PDF OCR 转换系统",
      "bbox": [120, 80, 900, 130],
      "confidence": 0.98
    },
    {
      "text": "本文介绍一种面向扫描版 PDF 的识别方法。",
      "bbox": [120, 180, 920, 220],
      "confidence": 0.95
    }
  ]
}
```

保留坐标非常重要，因为后续版面分析、排序和 Word 还原都依赖坐标。

## 6. 版面分析策略

### 6.1 基础规则版

基础版本可以先基于坐标规则实现：

- 根据文字框高度判断标题。
- 根据字号近似值和文本长度判断段落。
- 根据 y 坐标聚合同一行。
- 根据 x 坐标识别多栏。
- 根据重复位置识别页眉页脚。
- 根据大面积非文字区域保留图片。

适合课程第一版快速完成。

### 6.2 多栏排序

多栏排序是杂志、论文处理的关键。

建议步骤：

1. 获取页面所有文本框。
2. 根据文本框中心点的 x 坐标聚类。
3. 判断页面是单栏还是双栏、多栏。
4. 每一栏内部按 y 坐标排序。
5. 栏之间按 x 坐标从左到右排序。

对于中文竖排或特殊设计排版，可作为项目限制说明。

### 6.3 页眉页脚过滤

页眉页脚通常具有以下特征：

- 位于页面顶部或底部固定区域。
- 多页重复出现。
- 字号较小。
- 内容与正文关联较弱。

处理方法：

- 统计多页相同或相似文本的位置。
- 若文本反复出现在顶部或底部，则标记为 header/footer。
- 导出 EPUB 和 Markdown 时默认过滤。
- 导出 DOCX 时可选择保留。

### 6.4 标题识别

标题可通过以下特征判断：

- 文本框高度较大。
- 位于页面上方或段落起始位置。
- 文本较短。
- 周围留白较多。
- 包含章节编号，如“第 1 章”“一、”“1.1”。

标题识别不需要追求绝对准确，课程项目中可以说明采用启发式规则。

### 6.5 表格识别

表格识别建议分阶段做：

- 基础版：保存表格区域截图。
- 增强版：使用 PaddleOCR PP-Structure 提取表格 HTML。
- 高级版：将表格转换为 DOCX 表格和 HTML 表格。

课程项目中建议至少实现“表格截图保留”，增强效果可以作为加分项。

## 7. 文档重建

OCR 原始结果通常是一堆文字行，不能直接导出为高质量文档。需要进行结构化重建。

重建步骤：

1. 合并同一段落的多行文本。
2. 标记标题、段落、表格、图片、页眉页脚。
3. 按阅读顺序排序。
4. 建立页面和内容块之间的关系。
5. 输出统一中间文档模型。

段落合并规则：

- 相邻行 x 坐标接近。
- 行间距小于阈值。
- 前一行末尾没有明显句号时优先合并。
- 缩进变化较大时可能是新段落。

## 8. 导出策略

### 8.1 导出 DOCX

DOCX 目标是便于编辑。

处理策略：

- 标题使用 Word 标题样式。
- 正文使用首行缩进。
- 图片按页面或区域插入。
- 表格优先转为 Word 表格，无法识别时插入截图。
- 页眉页脚可选择保留。

### 8.2 导出 EPUB

EPUB 目标是便于阅读。

处理策略：

- 按章节拆分 XHTML。
- 过滤页眉页脚和页码。
- 图片插入正文对应位置。
- 表格可以转 HTML 表格。
- 不追求固定版式，重点保证阅读顺序。

### 8.3 导出 HTML

HTML 适合作为预览和调试格式。

处理策略：

- 显示识别文本。
- 可选显示文本框边界。
- 支持高亮低置信度文字。
- 用于评估 OCR 效果。

## 9. 转换质量评估

为了让项目更有深度，建议加入转换质量评估指标：

- OCR 平均置信度
- 低置信度文本数量
- 页面处理耗时
- 文本块数量
- 图片保留数量
- 表格识别数量
- 页眉页脚过滤数量

这些指标可以显示在前端任务详情页，也可以写入课程报告。

## 10. 项目限制

应在报告中明确说明：

- 复杂艺术排版无法完全还原。
- OCR 对低清晰度、倾斜、手写体内容识别效果有限。
- EPUB 更适合重排阅读，不适合原版式复刻。
- DOCX 可以保留更多结构，但无法保证与原 PDF 像素级一致。

## 11. 当前代码中的实操流程

当前项目已经不是“整页直接 OCR”的实现方式，而是先做页面渲染和版面分析，再对需要识别的文本块进行裁剪识别。这样可以减少无效区域识别，也方便后续按块重建文档结构。

实际流水线如下：

```text
上传文件
  ↓
render：将 PDF 或图片转成页面 PNG
  ↓
layout_detect：使用 PaddleOCR LayoutDetection 做原始版面检测
  ↓
layout_refine：把原始版面框转换成项目内部 block 结构
  ↓
ocr：只对 title、subtitle、body、caption 等文本块做 OCR
  ↓
text_cleaning：清洗和合并文本
  ↓
document_build：生成中间阅读稿
  ↓
export：导出 DOCX、EPUB、Markdown 等格式
```

对应入口在 `backend/app/workers/tasks.py` 的 `process_uploaded_task()` 中。OCR 阶段实际调用的是：

```python
run_task_ocr(
    task_dir=task_dir,
    cache_dir=Path(settings.paddlex_cache_root),
    padding=4,
    include_unknown=False,
    save_crops=False,
    use_textline_orientation=False,
)
```

这些参数的含义如下：

- `padding=4`：裁剪文本块时向外扩 4 像素，避免文字边缘被切掉。
- `include_unknown=False`：默认不识别未知类型块，减少误识别和耗时。
- `save_crops=False`：默认不保留裁剪小图，降低磁盘占用。
- `use_textline_orientation=False`：默认不开启文字行方向模型，避免额外模型加载和 CPU 压力。

## 12. 本地 OCR 的执行步骤

### 12.1 准备任务目录

任务文件统一放在：

```text
backend/storage/tasks/{task_id}
```

其中常见子目录如下：

```text
input/          原始上传文件
pages/          渲染后的页面图片
layout_raw/     原始版面检测结果
layout/         规则修正后的版面结构
ocr/            OCR 识别结果
debug/          版面检测调试图
```

OCR 阶段依赖 `layout/page_*.json`，因此不能跳过前面的渲染、版面检测和版面修正步骤。

### 12.2 单独运行 OCR

如果只想调试 OCR 阶段，可以在项目根目录执行：

```bash
conda run -n industrial-cv python backend/app/modules/ocr.py {task_id}
```

如果需要保留每个文本块的裁剪图，便于查看识别失败原因，可以加上：

```bash
conda run -n industrial-cv python backend/app/modules/ocr.py {task_id} --save-crops
```

如果遇到旋转文字较多的材料，再尝试：

```bash
conda run -n industrial-cv python backend/app/modules/ocr.py {task_id} --use-textline-orientation
```

这个选项可能触发额外模型加载，Mac 本地调试时不建议默认开启。

### 12.3 查看 OCR 输出

每页结果写入：

```text
backend/storage/tasks/{task_id}/ocr/page_001.json
backend/storage/tasks/{task_id}/ocr/page_002.json
...
```

汇总结果写入：

```text
backend/storage/tasks/{task_id}/ocr/summary.json
```

单页结果中重点看：

- `blocks`：被识别的文本块。
- `lines`：PaddleOCR 返回的行级文本、坐标和置信度。
- `ocr_confidence`：当前文本块平均置信度。
- `timing`：裁剪、保存、预测、清理分别花了多少时间。
- `skipped_blocks`：被跳过的图片、表格、页眉、页脚、页码等块。

汇总结果中重点看：

- `avg_confidence`：整体平均置信度。
- `low_confidence_block_count`：低置信度块数量。
- `total_ocr_seconds`：OCR 总耗时。
- `ocr_model_init_seconds`：模型初始化耗时。
- `slow_blocks`：耗时较长的文本块，适合定位性能问题。

## 13. 本地 OCR 与云端文档解析的混合方案

Mac 本地运行 Paddle 模型时，CPU 和内存压力会比较明显。后续建议采用“简单任务本地处理，复杂任务走云端 API”的混合方案，而不是把所有文件都压在本机模型上。

### 13.1 模式设计

建议在任务中增加一个处理模式：

```text
local：强制本地 PaddleOCR
cloud：强制百度智能文档分析平台
auto：系统自动判断
```

第一阶段先做 `local` 和 `cloud` 的手动选择，等链路稳定后再做 `auto`。

### 13.2 自动判断规则

`auto` 模式可以先用简单规则实现，不需要一开始就做复杂模型判断：

- 页数较少、主要是普通文字：走本地。
- 页数较多：走云端。
- 表格、公式、图表、印章较多：走云端。
- 本地版面分析后 `need_vlm_page_count` 较高：走云端。
- 用户电脑处于明显高负载时：优先建议云端。
- 涉及隐私文件时：默认本地，除非用户主动选择云端。

### 13.3 百度接口接入步骤

百度文档解析（PaddleOCR-VL）是异步接口，接入时不要让前端直接访问百度接口，API Key、Secret Key 和 access_token 都应只放在后端。

后端建议新增：

```text
backend/app/services/ocr_providers/
  __init__.py
  base.py
  local_paddle.py
  baidu_document.py
```

其中 `base.py` 定义统一接口：

```python
class OcrProvider:
    def submit(self, task_dir: Path) -> dict:
        ...

    def wait_result(self, provider_task_id: str) -> dict:
        ...

    def normalize(self, provider_result: dict, task_dir: Path) -> dict:
        ...
```

百度云端实现步骤：

1. 从环境变量读取 `BAIDU_OCR_API_KEY` 和 `BAIDU_OCR_SECRET_KEY`。
2. 后端获取并缓存 `access_token`，避免每次任务重复鉴权。
3. 将原始 PDF 通过 `file_data` 或 `file_url` 提交到百度文档解析接口。
4. 接口返回百度侧 `task_id` 后，将它记录到本项目任务的扩展信息中。
5. 按官方建议间隔查询结果，不要高频轮询。
6. 任务成功后下载 `parse_result_url` 的 JSON，同时可保存 `markdown_url` 便于调试。
7. 将百度返回的 `pages`、`layouts`、`tables`、`images` 转换成项目内部统一结构。
8. 后续 `text_cleaning`、`document_build`、`export` 尽量复用现有流程。

### 13.4 结果转换策略

百度返回的 JSON 已经包含页面、版面元素、文本、坐标、表格和图片信息。为了不让后续模块感知本地或云端差异，应转换成和本地 OCR 接近的结构：

```text
百度 pages[].layouts
  ↓
项目 layout/page_*.json 中的 blocks
  ↓
项目 ocr/page_*.json 中的 blocks + lines
  ↓
text_cleaning 和 document_build 继续处理
```

类型映射建议如下：

| 百度类型 | 项目内部 role |
| --- | --- |
| doc_title、title | title |
| paragraph_title | subtitle |
| text、abstract、reference_content | body |
| table | table |
| image、chart | figure |
| header | header |
| footer、number | footer |
| display_formula、inline_formula | formula |

表格优先使用百度返回的 Markdown；如果后续要导出 DOCX 表格，再把 Markdown 表格转换为 Word 表格。

### 13.5 数据库与任务状态

为方便排查和恢复，建议给任务增加以下字段，或者先放进已有的 `summary_json` 里过渡：

```text
processing_mode       local / cloud / auto
ocr_provider          paddle / baidu_paddle_vl
provider_task_id      百度侧 task_id
provider_status       pending / processing / success / failed
provider_error        云端错误信息
provider_result_path  下载后的 JSON 文件路径
```

任务状态仍然使用项目已有的阶段状态：

```text
render
layout_detect
layout_refine
ocr
text_cleaning
document_build
export
```

云端模式下，`ocr` 阶段内部可以拆成“提交云端任务、等待结果、下载结果、转换结构”四步，但前端不需要新增复杂流程，只显示 OCR 阶段正在处理即可。

### 13.6 风险控制

云端方案能明显降低本地 CPU 压力，但需要处理几个问题：

- 网络失败：任务要能标记失败，并保留百度侧错误信息。
- 额度不足：返回给用户明确提示，不要只显示“处理失败”。
- 大文件上传：超过限制时改用 `file_url`，不要强行 base64。
- 隐私问题：前端必须提示用户“云端处理会上传文件到第三方服务”。
- 结果有效期：`markdown_url` 和 `parse_result_url` 有有效期，项目应尽快下载并落盘。
- 成本控制：`auto` 模式不要把所有任务都丢给云端，避免费用失控。

## 14. 后续落地顺序

建议按下面顺序实现，风险最低：

1. 保留现有本地 OCR，不改当前成功路径。
2. 增加后端配置项和 `.env.example` 示例，不提交真实密钥。
3. 新增百度 provider，只实现“提交任务、查询结果、下载 JSON”。
4. 做一个命令行脚本先跑通单文件云端解析。
5. 把百度 JSON 转换成本项目的 `ocr/page_*.json` 和 `ocr/summary.json`。
6. 在前端上传区域增加处理模式选择：本地、云端、自动。
7. 在 Celery 流水线中根据模式选择本地 provider 或百度 provider。
8. 最后再做 `auto` 判断和失败回退。

这套顺序的好处是：本地链路一直可用，云端链路可以独立验证，出现问题时也容易定位是提交、查询、下载，还是结果转换出了问题。

## 15. 百度云端解析脚本实操

当前已新增一个独立命令行脚本：

```text
backend/scripts/baidu_paddle_vl_parse.py
```

这个脚本只负责单文件云端解析验证，不接入 Celery，不影响现有本地 PaddleOCR 流水线。

### 15.1 环境变量

本地 `.env` 中配置：

```bash
BAIDU_OCR_API_KEY=你的 API Key
BAIDU_OCR_SECRET_KEY=你的 Secret Key
```

也可以直接提供 `BAIDU_OCR_ACCESS_TOKEN`，脚本会优先使用 access token；没有 token 时再用 API Key 和 Secret Key 自动换取。

真实密钥不要写入 `.env.example`，也不要提交到仓库。

### 15.2 云端解析单文件

在项目根目录执行：

```bash
conda run -n industrial-cv python backend/scripts/baidu_paddle_vl_parse.py \
  backend/storage/tasks/9f4a8981fb4d46ce91eff363c2b1023b/input/poet.jpg \
  --task-id baidu_poet_cloud_test \
  --poll-interval 8 \
  --timeout-seconds 300
```

执行过程：

1. 读取本地文件并进行 base64 编码。
2. 调用百度提交接口，获取百度侧 `task_id`。
3. 每 8 秒查询一次任务状态。
4. 成功后下载 `parse_result_url` 中的 JSON。
5. 如果存在 `markdown_url`，同时保存 Markdown。
6. 将百度 JSON 转成本项目适配的 `layout` 和 `ocr` JSON。

### 15.3 输出目录

脚本会生成：

```text
backend/storage/tasks/{task_id}/
  input/                         原始输入文件副本
  cloud/
    baidu_submit_response.json   百度提交响应
    baidu_query_response.json    百度查询响应
    baidu_parse_result.json      百度原始解析 JSON
    baidu_result.md              百度 Markdown 结果
  layout/
    page_001.json                项目适配版面 JSON
    summary.json
  ocr/
    page_001.json                项目适配 OCR JSON
    summary.json
  metadata.json
```

其中 `layout/page_*.json` 和 `ocr/page_*.json` 是后续清洗和文档构建模块实际读取的文件。

### 15.4 离线转换已有百度 JSON

如果已经下载了百度 `parse_result_url` 的 JSON，可以跳过云端调用，只做格式转换：

```bash
conda run -n industrial-cv python backend/scripts/baidu_paddle_vl_parse.py \
  --raw-json /path/to/baidu_parse_result.json \
  --output-task-dir /private/tmp/baidu_paddle_vl_sample_task
```

这个模式适合调试字段映射，不消耗百度额度。

### 15.5 验证后续链路

转换完成后，可以继续运行本项目已有清洗和文档构建：

```bash
conda run -n industrial-cv python backend/app/modules/text_cleaning.py backend/storage/tasks/baidu_poet_cloud_test
conda run -n industrial-cv python backend/app/modules/document_build.py backend/storage/tasks/baidu_poet_cloud_test
```

本次真实测试中，`poet.jpg` 云端任务提交成功，百度任务状态从 `running` 变为 `success`，最终生成：

```text
backend/storage/tasks/baidu_poet_cloud_test/ocr/summary.json
backend/storage/tasks/baidu_poet_cloud_test/clean/document.json
backend/storage/tasks/baidu_poet_cloud_test/clean/book.md
```

清洗阶段能正常读取云端转换结果，说明这个格式已经可以接到后续文本清洗和文档构建流程。
