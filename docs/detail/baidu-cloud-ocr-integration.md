# 百度云端 OCR 融合说明

本文记录“本地 PaddleOCR + 百度文档解析 PaddleOCR-VL”混合处理的接入方式，方便后续继续维护和扩展。

## 1. 改造目标

Mac 本地运行 PaddleOCR 和版面检测模型时，CPU 压力较大。现在系统支持三种处理模式：

```text
auto   自动判断
local  本地识别
cloud  云端增强
```

第一阶段的自动判断规则很简单：

```text
PDF   -> cloud
图片  -> local
```

这样 PDF 默认走百度云端，降低本机压力；单张图片仍保留本地识别，避免所有任务都依赖网络和第三方服务。

## 2. 前端变化

修改文件：

```text
UI/src/App.tsx
UI/src/styles.css
```

上传表单的高级选项里新增处理模式选择：

- 自动判断：PDF 云端，图片本地。
- 本地识别：完全使用本地 PaddleOCR。
- 云端增强：使用百度 PaddleOCR-VL 文档解析。

提交上传时，前端会在 `FormData` 中增加：

```text
processing_mode=auto|local|cloud
```

同时原来的字段保持不变：

```text
file
output_format
auto_start
```

## 3. 上传接口变化

修改文件：

```text
backend/app/api/tasks.py
```

接口：

```text
POST /api/tasks/upload
```

新增表单字段：

```text
processing_mode: auto | local | cloud
```

为了避免现在改 MySQL 表结构，处理模式不写入 `tasks` 表，而是写入任务目录的：

```text
backend/storage/tasks/{task_id}/metadata.json
```

示例：

```json
{
  "task_id": "xxx",
  "original_name": "demo.pdf",
  "input_type": "pdf",
  "output_format": "epub,markdown",
  "processing_mode": "auto",
  "processing_mode_requested": "auto"
}
```

Celery 真正开始处理时，会把 `auto` 解析成实际模式，并更新同一个文件：

```json
{
  "processing_mode_requested": "auto",
  "processing_mode": "cloud",
  "processing_provider": "baidu_paddle_vl"
}
```

## 4. 后端云端模块

新增文件：

```text
backend/app/modules/baidu_paddle_vl.py
```

这个模块负责：

1. 读取百度 AK/SK 或 access token。
2. 提交文件到百度 PaddleOCR-VL。
3. 轮询任务状态。
4. 下载 `parse_result_url` 的原始 JSON。
5. 可选下载 `markdown_url` 的 Markdown。
6. 将百度 JSON 转换成本项目的 `layout/ocr` JSON。

命令行脚本：

```text
backend/scripts/baidu_paddle_vl_parse.py
```

现在只是一个薄包装，也调用同一个模块。这样 Celery 和命令行不会维护两套转换逻辑。

## 5. Celery 流水线变化

修改文件：

```text
backend/app/workers/tasks.py
```

任务开始后先读取：

```text
task_dir/metadata.json
```

然后决定实际模式：

```text
local -> 本地 Paddle 流水线
cloud -> 百度云端流水线
auto  -> PDF 用 cloud，图片用 local
```

### 5.1 本地模式

本地模式保持原流程：

```text
render
layout_detect
layout_refine
ocr
text_cleaning
document_build
export
```

其中 `layout_detect` 和 `ocr` 会加载 Paddle 相关模型。

### 5.2 云端模式

云端模式仍保留 `render`：

```text
render
ocr(百度云端解析 + 结果转换)
text_cleaning
document_build
export
```

保留 `render` 的原因是前端处理页需要显示原文预览图。页面渲染比本地 Paddle 模型轻很多，一般不会造成明显 CPU 压力。

云端模式下：

- `layout_detect` 标记为 `skipped`。
- `layout_refine` 标记为 `skipped`。
- `ocr` 阶段内部调用百度接口，并生成项目适配 JSON。

## 6. 百度凭证配置

`.env.example` 已增加占位字段：

```bash
BAIDU_OCR_API_KEY=
BAIDU_OCR_SECRET_KEY=
BAIDU_OCR_ACCESS_TOKEN=
```

本地 `.env` 写真实值即可。不要把真实密钥提交到仓库。

优先级：

```text
BAIDU_OCR_ACCESS_TOKEN > BAIDU_OCR_API_KEY + BAIDU_OCR_SECRET_KEY
```

如果提供了 access token，系统直接使用；否则用 API Key 和 Secret Key 自动换取 token。

## 7. 输出目录

云端模式会生成：

```text
backend/storage/tasks/{task_id}/
  cloud/
    baidu_submit_response.json
    baidu_query_response.json
    baidu_parse_result.json
    baidu_result.md
  layout/
    page_001.json
    page_002.json
    summary.json
  ocr/
    page_001.json
    page_002.json
    summary.json
  clean/
    cleaning_report.json
    document.json
    book.md
```

其中：

- `cloud/baidu_parse_result.json` 是百度原始结构。
- `layout/page_*.json` 是适配项目版面结构后的结果。
- `ocr/page_*.json` 是适配项目 OCR 结构后的结果。
- `clean/document.json` 和 `clean/book.md` 由原有清洗和文档构建模块生成。

## 8. 手工测试方法

### 8.1 前端测试

1. 启动后端、Redis、Celery worker、前端。
2. 打开前端首页。
3. 展开“高级选项”。
4. 选择“云端增强”或“自动判断”。
5. 上传 PDF。
6. 等待任务完成。
7. 查看清洗文本和导出结果。

### 8.2 命令行测试云端转换

不经过前端，直接测试百度云端解析：

```bash
conda run -n industrial-cv python backend/scripts/baidu_paddle_vl_parse.py \
  backend/storage/tasks/manual_pdf_pipeline_test/input/pdf1.0.pdf \
  --task-id baidu_pdf1_cloud_test \
  --poll-interval 8 \
  --timeout-seconds 900
```

如果已有百度原始 JSON，只想离线转换：

```bash
conda run -n industrial-cv python backend/scripts/baidu_paddle_vl_parse.py \
  --raw-json backend/storage/tasks/baidu_pdf1_cloud_test/cloud/baidu_parse_result.json \
  --output-task-dir backend/storage/tasks/baidu_pdf1_cloud_test
```

### 8.3 验证后续链路

```bash
conda run -n industrial-cv python backend/app/modules/text_cleaning.py backend/storage/tasks/baidu_pdf1_cloud_test
conda run -n industrial-cv python backend/app/modules/document_build.py backend/storage/tasks/baidu_pdf1_cloud_test
```

## 9. 当前限制

第一阶段还没有做以下内容：

- 没有把 `processing_mode` 加入数据库字段。
- 任务列表暂不直接展示处理模式。
- `auto` 判断规则还比较简单，只按文件类型判断。
- 云端失败后暂不自动回退本地。
- 百度接口调用仍在 Celery 任务内部等待完成，长文档会占用一个 worker。

后续可以继续做：

- 增加数据库字段，方便任务列表展示和筛选。
- `auto` 根据页数、表格数量、复杂版面比例判断。
- 百度失败后可选回退本地。
- 将百度异步任务拆成独立 Celery 子任务，减少单个 worker 长时间阻塞。
