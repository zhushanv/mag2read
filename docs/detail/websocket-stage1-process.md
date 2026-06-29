# WebSocket 第一阶段改造说明

本文记录本次从前端固定轮询改为 WebSocket 状态通道的实现过程，方便后续继续优化。

## 1. 改造目标

原来的前端在 `UI/src/App.tsx` 中使用 `setInterval`，每 2.5 秒请求一次任务列表；如果选中了任务，还会同时请求任务详情、步骤、导出记录和文件列表。

这个方案的问题是：

- 页面空闲时也会持续请求。
- 后端未启动时会持续报错重试。
- 处理页打开时每轮请求数量较多。
- 用户电脑会因为持续轮询、日志输出和动画叠加出现额外负载。

第一阶段目标不是做完整事件总线，而是先把高频前端轮询替换为单任务 WebSocket 状态通道。

## 2. 当前实现方案

本阶段采用：

```text
前端 WebSocket 连接 /ws/tasks/{task_id}
        ↓
后端连接期间每 1.5 秒查询该任务状态
        ↓
只有状态变化时才推送 task + steps
        ↓
前端更新当前任务进度和流程节点
        ↓
任务结束后前端补拉一次完整详情
```

这里仍然保留 REST API。WebSocket 只负责实时状态，不承载页面图片、OCR JSON、导出文件等大数据。

## 3. 后端改动

新增文件：

```text
backend/app/api/task_events.py
```

新增端点：

```text
GET WebSocket /ws/tasks/{task_id}
```

核心逻辑：

1. 客户端连接后，后端 `accept()`。
2. 后端通过 `SessionLocal()` 查询当前 task 和 task steps。
3. 使用 `TaskRead` 和 `TaskStepRead` 转成 JSON 可序列化结构。
4. 对关键字段计算签名：
   - task status
   - current stage
   - progress
   - page count
   - error message
   - task updated/finished time
   - steps 的 stage/status/progress/duration/error/updated time
5. 签名变化才发送消息，避免无变化时重复推送。
6. 如果任务进入 `success`、`failed`、`cancelled`，发送最后一次状态后关闭连接。

消息格式：

```json
{
  "type": "task_update",
  "task": {
    "task_id": "...",
    "status": "processing",
    "current_stage": "ocr",
    "progress": 65
  },
  "steps": [
    {
      "stage": "ocr",
      "status": "processing",
      "progress": 0
    }
  ]
}
```

如果任务不存在：

```json
{
  "type": "task_missing",
  "task_id": "..."
}
```

并关闭连接。

`backend/app/main.py` 中新增了 `task_events_router` 注册。

## 4. 前端改动

修改文件：

```text
UI/src/App.tsx
UI/vite.config.ts
```

`App.tsx` 中删除了原来的固定轮询：

```ts
window.setInterval(...)
```

改为在 `selectedTaskId` 存在时建立 WebSocket：

```ts
const socket = new WebSocket(websocketUrl(`/ws/tasks/${selectedTaskId}`));
```

收到 `task_update` 后：

1. 更新当前 `bundle.task`。
2. 更新当前 `bundle.steps`。
3. 同步更新首页任务列表中对应任务的状态。
4. 如果任务进入终态，调用 `loadTaskBundle()` 和 `loadTasks()` 补拉一次完整数据。

为什么终态还要补拉一次？

WebSocket 只推 task 和 steps，不推 exports、files、clean document。任务完成时需要完整详情来显示导出文件、完成页指标和下载入口，所以终态补拉一次 REST 是合理的。

## 5. Vite 开发代理

`UI/vite.config.ts` 增加了 `/ws` 代理：

```ts
"/ws": {
  target: "ws://127.0.0.1:8000",
  ws: true
}
```

这样开发时前端可以连接：

```text
ws://127.0.0.1:5173/ws/tasks/{task_id}
```

由 Vite 转发到后端：

```text
ws://127.0.0.1:8000/ws/tasks/{task_id}
```

生产部署时，如果前后端同源，`websocketUrl()` 会自动使用当前页面的 host 和协议生成 `ws://` 或 `wss://` 地址。

## 6. 性能收益

改造前：

- 首页固定每 2.5 秒请求任务列表。
- 处理页每 2.5 秒请求任务列表 + 任务详情 + steps + exports + files。
- 后端未启动时也持续失败重试。

改造后：

- 首页只在首次进入、上传后、手动刷新时请求任务列表。
- 处理页只维护一个 WebSocket 连接。
- 后端只有状态变化时才推送消息。
- 任务结束后连接自动关闭。

这能明显减少空闲状态下的请求量和失败日志量。

## 7. 当前阶段的限制

第一阶段仍然不是完全事件驱动，因为 FastAPI WebSocket 端点内部仍然每 1.5 秒查一次数据库。

但这个轮询发生在：

- 单个任务维度
- 后端内部
- 只连接期间存在
- 只在状态变化时发消息

相比浏览器全局高频请求，负载已经小很多。

## 8. 后续升级方向

第二阶段可以引入 Redis pub/sub：

```text
Celery worker 完成阶段
        ↓
写数据库
        ↓
Redis publish task_update
        ↓
FastAPI WebSocket 订阅 Redis
        ↓
实时推送前端
```

这样 WebSocket 端点不需要查库循环，真正变成事件驱动。

也可以进一步增加一个聚合 REST 接口：

```text
GET /api/tasks/{task_id}/bundle
```

一次返回：

- task
- steps
- files
- exports

这样终态补拉也只需要一个请求。

## 9. 验证方式

前端构建：

```bash
cd UI
npm run build
```

后端语法检查：

```bash
conda run -n industrial-cv python -m py_compile backend/app/api/task_events.py backend/app/main.py
```

手工验证：

1. 启动后端。
2. 启动前端。
3. 上传一个任务。
4. 打开浏览器开发者工具 Network，查看是否有 `/ws/tasks/{task_id}`。
5. 确认不再出现每 2.5 秒一组 REST 轮询请求。
6. 任务完成后，确认 WebSocket 自动关闭，完成页导出文件正常显示。
