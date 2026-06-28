# 阶段 0 手动测试文档

## 1. 测试目标

阶段 0 的目标是验证项目基础设施是否可用。

需要手动确认：

- 后端依赖可以安装。
- `.env` 配置可以被读取。
- MySQL 数据库可以初始化。
- Redis 可以连接。
- FastAPI 可以启动。
- 健康检查接口可以返回 API、MySQL、Redis 状态。
- Celery Worker 可以启动并执行最小 ping 任务。
- 原有后端核心模块没有被破坏。

本阶段不做完整 OCR 流程测试。

## 2. 涉及文件

阶段 0 新增或相关文件：

```text
.env.example
backend/requirements.txt
environment.yml
backend/app/main.py
backend/app/api/health.py
backend/app/core/config.py
backend/app/core/database.py
backend/app/core/redis_client.py
backend/app/workers/celery_app.py
backend/app/workers/tasks.py
backend/database/init_mysql.sql
```

## 3. 准备环境

进入项目目录：

```bash
cd /Users/zhu/projects/python-project/课程项目2
```

建议继续使用当前项目的 conda 环境：

```bash
conda activate industrial-cv
```

如果依赖没有安装，执行：

```bash
pip install -r backend/requirements.txt
```

也可以使用：

```bash
conda run -n industrial-cv pip install -r backend/requirements.txt
```

## 4. 配置环境变量

复制配置模板：

```bash
cp .env.example .env
```

编辑 `.env`：

```bash
vim .env
```

至少确认这些字段：

```text
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=你的MySQL密码
MYSQL_DATABASE=mag2read

REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
```

注意：不要把真实数据库密码写入文档或提交到代码仓库。

## 5. 初始化 MySQL

确认 MySQL 已启动。

如果使用 Homebrew 安装 MySQL，可以检查：

```bash
brew services list
```

执行初始化脚本：

```bash
mysql -u root -p < backend/database/init_mysql.sql
```

输入 MySQL root 密码后，检查数据库：

```bash
mysql -u root -p
```

进入 MySQL 后执行：

```sql
SHOW DATABASES;
USE mag2read;
SHOW TABLES;
SELECT username, role FROM users;
```

预期结果：

```text
mag2read 数据库存在
users 表存在
tasks 表存在
task_files 表存在
task_pages 表存在
task_steps 表存在
export_records 表存在
users 表中存在 admin 用户
```

## 6. 启动 Redis

确认 Redis 已启动。

如果使用 Homebrew：

```bash
brew services start redis
```

检查 Redis：

```bash
redis-cli ping
```

预期结果：

```text
PONG
```

## 7. 启动 FastAPI

在项目根目录执行：

```bash
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

如果使用 conda run：

```bash
conda run -n industrial-cv uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

浏览器打开：

```text
http://127.0.0.1:8000/
```

预期结果：

```json
{
  "name": "Mag2Read",
  "status": "running"
}
```

## 8. 测试健康检查接口

新开一个终端，执行：

```bash
curl http://127.0.0.1:8000/api/health
```

如果 MySQL 和 Redis 都正常，预期返回类似：

```json
{
  "status": "ok",
  "services": {
    "api": {
      "ok": true,
      "message": "FastAPI is running"
    },
    "database": {
      "ok": true,
      "message": "MySQL connection ok"
    },
    "redis": {
      "ok": true,
      "message": "Redis connection ok"
    }
  }
}
```

如果 MySQL 或 Redis 没启动，`status` 会是：

```text
degraded
```

这说明 API 本身正常，但外部服务未完全连通。

## 9. 启动 Celery Worker

确保 Redis 正在运行。

新开一个终端，在项目根目录执行：

```bash
celery -A backend.app.workers.celery_app.celery_app worker --loglevel=info
```

如果使用 conda run：

```bash
conda run -n industrial-cv celery -A backend.app.workers.celery_app.celery_app worker --loglevel=info
```

预期现象：

```text
worker 启动成功
能看到 registered tasks 中包含 stage0.ping
```

## 10. 手动发送 Celery Ping 任务

保持 Celery Worker 运行。

另开终端执行：

```bash
python -c "from backend.app.workers.tasks import ping; r = ping.delay(); print(r.get(timeout=10))"
```

如果使用 conda run：

```bash
conda run -n industrial-cv python -c "from backend.app.workers.tasks import ping; r = ping.delay(); print(r.get(timeout=10))"
```

预期结果：

```text
pong
```

## 11. 检查原有核心模块入口

阶段 0 不要求跑完整 OCR，但需要确认原 CLI wrapper 没被破坏。

执行：

```bash
python backend/scripts/render_pdf_pages.py --help
python backend/scripts/analyze_layout.py --help
python backend/scripts/refine_layout.py --help
python backend/scripts/run_ocr.py --help
python backend/scripts/clean_text.py --help
python backend/scripts/build_document.py --help
python backend/scripts/export_document.py --help
```

如果使用 conda run：

```bash
conda run -n industrial-cv python backend/scripts/render_pdf_pages.py --help
```

预期结果：

```text
每个命令都能正常打印 help 信息
```

## 12. 阶段 0 验收清单

完成以下检查即可认为阶段 0 通过：

- [ ] `pip install -r backend/requirements.txt` 成功。
- [ ] `.env` 已创建，且 MySQL/Redis 配置正确。
- [ ] `backend/database/init_mysql.sql` 执行成功。
- [ ] MySQL 中存在 `mag2read` 数据库和 6 张表。
- [ ] `redis-cli ping` 返回 `PONG`。
- [ ] FastAPI 能通过 `uvicorn backend.app.main:app --reload` 启动。
- [ ] `GET /` 返回 `Mag2Read` 和 `running`。
- [ ] `GET /api/health` 返回 API、MySQL、Redis 状态。
- [ ] Celery Worker 能启动。
- [ ] `stage0.ping` 返回 `pong`。
- [ ] 原有脚本入口 `--help` 正常。

## 13. 常见问题

### 13.1 FastAPI 启动时报 `ModuleNotFoundError`

先确认在项目根目录执行命令：

```bash
pwd
```

应该输出：

```text
/Users/zhu/projects/python-project/课程项目2
```

再确认依赖是否安装：

```bash
pip install -r backend/requirements.txt
```

### 13.2 健康检查返回 database failed

检查：

- MySQL 是否启动。
- `.env` 中 MySQL 密码是否正确。
- 是否执行过 `backend/database/init_mysql.sql`。
- 数据库名是否为 `mag2read`。

### 13.3 健康检查返回 redis failed

检查：

```bash
redis-cli ping
```

如果没有返回 `PONG`，先启动 Redis。

### 13.4 Celery 任务一直等待

检查：

- Redis 是否启动。
- Worker 是否正在运行。
- Worker 命令是否使用了正确的 app 路径：

```bash
celery -A backend.app.workers.celery_app.celery_app worker --loglevel=info
```

## 14. 下一阶段入口

阶段 0 通过后，进入阶段 1：

```text
数据库与任务模型
```

阶段 1 要实现：

- SQLAlchemy ORM 模型。
- Pydantic schemas。
- 任务状态枚举。
- 任务服务层。
- 任务查询 API。
