# 实操开发指南

## 1. 开发路线

建议按四个阶段完成，而不是一开始就追求完整复杂功能。

### 第一阶段：最小可运行系统

目标：完成上传、创建任务、OCR 识别、TXT 导出。

功能：

- React 上传 PDF。
- FastAPI 接收文件。
- 后端保存文件。
- PyMuPDF 将 PDF 渲染为图片。
- PaddleOCR 识别页面文字。
- 导出 TXT。
- 前端下载结果。

### 第二阶段：异步任务和历史记录

目标：解决 OCR 耗时问题，让系统像真实应用。

功能：

- Redis + Celery/RQ。
- 任务状态查询。
- 进度条。
- 转换历史列表。
- 失败任务错误提示。

### 第三阶段：文档结构重建和多格式导出

目标：从“识别文字”升级为“转换文档”。

功能：

- 中间文档模型。
- 段落合并。
- 标题识别。
- DOCX 导出。
- HTML 导出。
- Markdown 导出。
- EPUB 导出。

### 第四阶段：复杂版面增强

目标：形成课程项目亮点。

功能：

- 多栏识别。
- 页眉页脚过滤。
- 图片区域保留。
- 表格区域识别。
- OCR 质量评估。
- 前端预览对比。

## 2. 后端初始化

推荐使用 Python 3.10 或 3.11。

依赖建议：

```text
fastapi
uvicorn
python-multipart
sqlalchemy
pydantic
redis
celery
pymupdf
paddleocr
paddlepaddle
opencv-python
python-docx
ebooklib
jinja2
beautifulsoup4
markdown
```

如果本机安装 PaddleOCR 较慢，可以先使用 Tesseract 或 EasyOCR 做原型，但最终展示建议使用 PaddleOCR。

## 3. 前端初始化

推荐命令：

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install antd axios @tanstack/react-query react-router-dom
```

前端页面建议：

- `/convert`：上传和转换。
- `/tasks/:id`：任务详情和进度。
- `/history`：历史记录。

## 4. 后端核心开发顺序

### 4.1 文件上传接口

先实现：

- 接收 PDF。
- 校验文件扩展名。
- 保存到 `storage/uploads/`。
- 创建任务记录。
- 返回任务 ID。

### 4.2 PDF 渲染模块

模块名建议：`pdf_renderer.py`

职责：

- 打开 PDF。
- 遍历页面。
- 渲染为 PNG。
- 返回页面图片路径列表。

### 4.3 OCR 模块

模块名建议：`ocr_engine.py`

职责：

- 初始化 OCR 引擎。
- 接收图片路径。
- 返回文字、坐标、置信度。

### 4.4 图像预处理模块

模块名建议：`image_preprocessor.py`

职责：

- 读取图片。
- 灰度化。
- 降噪。
- 二值化。
- 保存增强后的图片。

### 4.5 文档构建模块

模块名建议：`document_builder.py`

职责：

- 合并 OCR 行。
- 标记标题和段落。
- 过滤页眉页脚。
- 输出中间文档模型。

### 4.6 导出模块

导出模块统一接收中间文档模型。

建议接口：

```python
class BaseExporter:
    def export(self, document: dict, output_path: str) -> str:
        raise NotImplementedError
```

不同格式分别实现：

- `TxtExporter`
- `MarkdownExporter`
- `HtmlExporter`
- `DocxExporter`
- `EpubExporter`

## 5. React 前端开发顺序

### 5.1 上传区

使用 Ant Design 的 `Upload.Dragger`。

页面元素：

- 文件拖拽上传区。
- 目标格式选择。
- OCR 语言选择。
- 启用版面分析开关。
- 开始转换按钮。

### 5.2 任务进度

使用轮询方式查询任务状态。

建议：

- 每 1 到 2 秒请求一次任务状态。
- 任务完成或失败后停止轮询。
- 成功后显示下载按钮。

### 5.3 历史记录

使用表格展示：

- 文件名
- 目标格式
- 任务状态
- 创建时间
- 耗时
- 下载按钮

### 5.4 结果预览

初期只预览 TXT 或 HTML。后期可以：

- HTML 内嵌预览。
- 显示每页 OCR 置信度。
- 对低置信度文本加颜色标记。

## 6. 推荐里程碑

### 第 1 周

- 搭建 React 和 FastAPI 项目。
- 完成 PDF 上传。
- 完成 PDF 渲染。

### 第 2 周

- 接入 PaddleOCR。
- 完成扫描版 PDF 转 TXT。
- 实现基础任务状态。

### 第 3 周

- 接入 Redis + Celery/RQ。
- 完成历史记录。
- 完成 HTML 和 Markdown 导出。

### 第 4 周

- 实现 DOCX 和 EPUB 导出。
- 实现标题识别、段落合并、页眉页脚过滤。

### 第 5 周

- 增加多栏排序和质量评估。
- 完善前端页面。
- 准备课程报告和答辩材料。

## 7. 最小可展示版本

如果时间紧，最低限度应完成：

- React 上传 PDF。
- 后端 OCR 扫描版 PDF。
- 转 TXT、DOCX。
- 显示任务进度。
- 保存转换历史。
- 下载转换结果。

这个版本已经能支撑课程演示。

## 8. 高分增强点

优先做这些增强：

- OCR 置信度统计。
- 多栏排版阅读顺序恢复。
- 低置信度文本高亮。
- DOCX 标题和段落样式。
- EPUB 章节拆分。
- 转换前后预览对比。
- Docker Compose 一键启动。

