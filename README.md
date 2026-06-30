# Mag2Read--智能杂志排版清洗与AI导读系统
学生群体和研究人员经常需要阅读杂志、期刊上的长文，但纸质版不便携带，扫描版PDF在电子阅读器上又存在排版混乱（多栏交错）、页眉页脚干扰、图表看不清等痛点。本项目作为一个Web系统，支持用户上传杂志扫描件（PDF/图片）后，自动提取正文，去除噪音，输出适合电子阅读器阅读的EPUB/Markdown文件，或者docx等可编辑文件。此外后期还会利用AI大模型辅助文档编辑。

---

## 项目结构

```
mag2read/
├── UI/                    # 前端 — React + Vite + TypeScript
│   ├── src/
│   │   ├── components/    # 页面组件（Doc3DPreview、PipelineFlow 等）
│   │   ├── App.tsx        # 主应用（首页、上传、任务面板、结果展示）
│   │   └── main.tsx       # 入口文件
│   ├── package.json
│   └── vite.config.ts
├── backend/               # 后端 — FastAPI + Celery + PaddleOCR
│   ├── app/
│   │   ├── api/           # 路由层（tasks、auth、exports、health）
│   │   ├── services/      # 业务逻辑（task_service、auth_service）
│   │   ├── modules/       # 核心模块（OCR、版面分析、文本清洗等）
│   │   ├── pipeline/      # 流水线编排（task_runner）
│   │   ├── models/        # SQLAlchemy 数据模型
│   │   ├── schemas/       # Pydantic 请求/响应模型
│   │   ├── workers/       # Celery 任务定义
│   │   └── main.py        # FastAPI 应用入口
│   ├── database/          # SQL 建表脚本
│   └── scripts/           # 独立测试脚本（布局检测、OCR、文档构建等）
├── docs/                  # 开发文档
│   ├── detail/            # 各模块详细文档
│   ├── explain/           # 技术说明
│   └── test/              # 手动测试用例
├── pdfs/                  # 测试用 PDF 和图片
├── environment.yml        # conda 环境配置
└── .env.example           # 环境变量模板
```

## 核心流程

一次完整的处理分成这几个阶段，按顺序跑：

1. **页面渲染** — 把 PDF 每一页转成图片
2. **版面分析** — 用 PaddleX 识别每页上的标题、正文、图片、表格、页眉页脚
3. **规则清洗** — 根据位置和重复模式去掉页眉页脚、页码这些噪点
4. **OCR 识别** — 对正文区域做文字识别，支持 PaddleOCR 和百度云 OCR
5. **文本整理** — 合并段落、修正空行、统一缩进
6. **文档构建** — 按阅读顺序组装成结构化文档
7. **格式导出** — 输出 EPUB / Markdown / DOCX / HTML / TXT

每个阶段都有独立模块，可以单独跑、单独测。处理过程通过 WebSocket 实时推送到前端，能看到当前跑到哪一步了。

## 快速上手

### 环境要求

- Python 3.10
- Node.js 18+
- MySQL 8.0+
- Redis

### 关于 Redis

Redis 是 Celery 任务队列的 broker，上传后自动处理需要它。如果你只是调试单个模块（比如单独跑版面分析脚本），不需要 Redis。但要做完整的「上传→自动处理→导出」流程，Redis 必须开着。

本地开发建议用 Docker 起一个：

```bash
docker run -d -p 6379:6379 redis:7
```

Mac 用户也可以用 Homebrew：

```bash
brew install redis && brew services start redis
```

跑起来之后不用管它。如果你之前一直在跑离线脚本做模块开发，那保持现状就行。


### 后端启动

```bash
# 创建 conda 环境
conda env create -f environment.yml
conda activate industrial-cv

# 初始化数据库
mysql -u root -p < backend/database/init_mysql.sql

# 复制环境变量并填写
cp .env.example .env

# 启动 FastAPI
uvicorn backend.app.main:app --reload --port 8000
```

### 前端启动

```bash
cd UI
npm install
npm run dev
```

### 启动 Celery Worker

```bash
conda activate industrial-cv
celery -A backend.app.workers.celery_app worker --loglevel=info
```

浏览器打开 `http://localhost:5173` 就能用了。

## 环境变量说明

核心配置都在 `.env` 文件里。`.env.example` 是模板，复制过去改就行：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `MYSQL_*` | 数据库连接信息 | localhost:3306/mag2read |
| `REDIS_*` | Redis 连接信息 | localhost:6379/0 |
| `BAIDU_OCR_*` | 百度云 OCR 密钥（可选） | 空 |
| `SMTP_*` | 邮件发送配置（可选） | 调试模式下返回验证码到 API 响应 |
| `AUTH_CODE_SECRET` | 验证码签名密钥 | 部署前一定要改 |

调试模式下（`DEBUG=true`），邮箱验证码不会真的发邮件，而是直接返回到接口响应里，方便开发。

## 各模块概览

### 前端

用 React + Vite 搭的单页应用，Three.js 做了 3D 的文档翻页效果。主要页面：

- **首页/登录** — 邮箱验证码或第三方 OAuth 登录
- **上传面板** — 拖拽上传、选择导出格式，开始转换
- **任务面板** — 实时进度、原文预览（带版面识别框叠加）、清洗后的阅读稿预览
- **结果面板** — 导出文件下载、内容预览
- **AI 导读** — 侧边栏，对识别结果做 AI 总结和追问

### 后端 API

FastAPI 应用，接口路径统一以 `/api` 开头：

| 路由 | 功能 |
|------|------|
| `/api/tasks` | 任务 CRUD、文件上传、处理进度 |
| `/api/exports` | 导出文件下载与内容预览 |
| `/api/auth` | 邮箱验证码登录、OAuth、会话管理 |
| `/api/health` | 服务健康检查（数据库、Redis） |
| `/ws/tasks/{id}` | WebSocket 实时推送任务状态 |

启动后端后访问 `http://localhost:8000/docs` 可以看完整的 OpenAPI 文档。

### 流水线模块（Pipeline）

`backend/app/pipeline/task_runner.py` 编排了整个处理流程。每个独立模块在 `backend/app/modules/` 下：

| 模块 | 文件 | 职责 |
|------|------|------|
| layout_detect | `modules/layout_detect.py` | 用 PaddleX 模型检测版面区域 |
| layout_refine | `modules/layout_refine.py` | 根据规则过滤页眉页脚等噪点 |
| ocr | `modules/ocr.py` | 执行 OCR，附带缓存和失败重试 |
| text_cleaning | `modules/text_cleaning.py` | 清洗文本、合并断行 |
| document_build | `modules/document_build.py` | 组装成结构化文档 |
| export_document | `modules/export_document.py` | 输出 EPUB/Markdown/DOCX 等 |

每个模块都有对应的 `scripts/` 脚本，可以在命令行单独跑，方便调试。

### 数据库

MySQL，主要表：

- `users` — 用户账号
- `tasks` — 转换任务主表
- `task_steps` — 每个阶段的执行记录
- `task_pages` — 每页的图片路径、版面类型、OCR 状态
- `task_files` — 任务相关的各类文件
- `export_records` — 导出记录
- `user_sessions` — 登录会话
- `email_verification_codes` — 邮箱验证码

建表脚本在 `backend/database/init_mysql.sql`。

## 开发指南

详细的 Git 协作流程在 `docs/Git协作开发指南.md`，这里说几个要点：

### 分支命名

- `feat/ui-xxx` — 前端功能
- `feat/api-xxx` — 后端接口
- `feat/ocr-xxx` — OCR 相关改动
- `fix/xxx` — 修 Bug
- `docs/xxx` — 文档更新

**main 分支不要直接提交**，都走分支 + Pull Request。

### 本地测试

处理单阶段的脚本在 `backend/scripts/` 下，例如：

```bash
# 单独跑版面分析
python -m backend.scripts.analyze_layout --task <task_id>

# 跑完整的转换流程
python -m backend.scripts.build_document --input pdfs/sample.pdf
```

手动测试用例在 `docs/test/` 下，每个阶段都有对应的 md 文件，按步骤验证就行。

### 给新同学的清单

1. 配置 Git 用户信息和 SSH 密钥
2. `git clone git@github.com:zhushanv/mag2read.git`
3. 按上面「快速上手」的步骤搭好本地环境
4. 跑一下 `python -m backend.scripts.analyze_layout --help` 确认后端能跑
5. 去 docs/ 翻一遍，重点看 `Git协作开发指南.md` 和对应自己负责模块的文档
6. 挑一个 issue 或者小功能，建分支开始干

## 测试数据

`pdfs/` 目录下有几份测试文件：

- `Scientific_American_-_July-August_2026.pdf` — 双栏杂志（主要测试用例）
- `British_Travel_Journal_-_Summer_2026.pdf` — 旅游杂志
- `DDCPC.pdf` — 中文字处理文档 PDF
- `complexLayout.jpg` / `table.jpg` / `handwrite.jpg` / `poet.jpg` — 不同场景的测试图片

## 技术栈

**后端**：Python 3.10 / FastAPI / SQLAlchemy / Celery / Redis / MySQL / PaddleOCR / PyMuPDF

**前端**：React 18 / TypeScript / Vite 5 / Three.js / Framer Motion / Lucide

**基础设施**：Conda / pip / npm / Celery

