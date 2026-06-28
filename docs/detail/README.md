# 基于 Python 的扫描版 PDF OCR 转换系统文档集

本目录用于整理课程结业项目的需求、架构和实操开发方案。项目重点不是简单地把 PDF 另存为其他格式，而是围绕“扫描版 PDF 的 OCR 识别、版面分析和多格式导出”构建一个完整的全栈系统。

## 项目定位

项目名称建议：

**基于 Python 与 React 的扫描版 PDF 智能 OCR 转换系统**

核心目标：

- 面向扫描版 PDF，完成文字识别、版面分析、结构化重组。
- 支持导出为 Word、EPUB、HTML、Markdown、TXT 等格式。
- 提供 React 前端页面，实现上传、任务进度、结果预览和文件下载。
- 后端采用 Python 技术栈，体现 OCR、异步任务、文件处理、数据持久化等工程能力。

## 文档说明

- [需求说明书](./requirements.md)：定义项目背景、用户需求、功能需求和非功能需求。
- [系统架构设计](./architecture.md)：说明前后端架构、模块划分、数据流和存储设计。
- [OCR 核心方案](./ocr-design.md)：重点说明扫描版 PDF 的 OCR 识别、版面分析和文档重建。
- [实操开发指南](./implementation-guide.md)：给出从 0 到可运行系统的开发步骤。
- [第一周实操文档](./week-1-practice.md)：聚焦扫描版 PDF OCR 主链路，列出每一步做法和验收成果。
- [接口设计文档](./api-design.md)：定义前后端交互 API。
- [课程展示与报告建议](./course-report-guide.md)：用于结业报告、答辩 PPT 和高分包装。

## 推荐最终交付

建议最终交付内容包括：

- React 前端项目
- FastAPI 后端项目
- OCR 转换核心模块
- SQLite 或 PostgreSQL 数据库
- Redis + Celery/RQ 异步任务
- 文件上传、转换、预览、下载功能
- 项目说明文档、测试样例、课程报告和演示视频
