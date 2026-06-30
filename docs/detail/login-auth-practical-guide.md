# Mag2Read 登录功能实操文档

## 1. 目标与设计取舍

Mag2Read 目前已经有 `users` 表和 `tasks.user_id` 字段，但用户体系还没有真正接入业务。登录功能的目标不是只做一个登录弹窗，而是把“用户身份、任务归属、历史记录隔离、第三方登录和安全校验”完整接入现有 FastAPI + MySQL + React 架构。

推荐采用“邮箱验证码登录注册一体化”为主流程：

- 用户输入邮箱。
- 后端发送 6 位验证码。
- 用户提交验证码。
- 若邮箱不存在则自动注册，存在则直接登录。
- 登录成功后签发访问令牌，并把后续上传任务绑定到该用户。

Google 登录、微信登录和人机验证作为增强能力接入。它们可以提高项目技术完整度，但不建议一开始就让所有能力互相耦合。实际实现顺序建议是：

1. 邮箱验证码登录。
2. 登录态保护任务接口。
3. Google OAuth 登录。
4. 人机验证。
5. 微信扫码登录。

这样每一步都能独立验收，不会把登录、第三方平台配置和前端状态管理混在一起。

## 2. 整体架构

```text
React 前端
  登录页 / 登录弹窗
  邮箱验证码表单
  Google 登录按钮
  微信登录入口
  AuthContext 保存当前用户
        |
        | HTTPS / JSON / Cookie
        v
FastAPI 后端
  /api/auth/request-code
  /api/auth/verify-code
  /api/auth/oauth/google/*
  /api/auth/oauth/wechat/*
  /api/auth/me
  /api/auth/logout
        |
        v
MySQL
  users
  email_verification_codes
  oauth_accounts
  user_sessions
  auth_audit_logs
        |
        v
邮件服务 / Google OAuth / 微信开放平台 / Turnstile 或 reCAPTCHA
```

登录后的任务访问规则：

- 未登录用户可以浏览首页。
- 上传、任务列表、任务详情、导出下载建议要求登录。
- `tasks.user_id` 必须写入当前登录用户 ID。
- 查询任务列表时只返回当前用户的任务。
- 访问任务详情、页面、文件、导出记录时必须校验任务归属。

## 3. 登录流程设计

### 3.1 邮箱验证码登录注册

这是主流程，适合课程项目落地，复杂度适中。

```text
用户输入邮箱
  -> 前端请求 /api/auth/email/request-code
  -> 后端校验邮箱格式、人机验证、频率限制
  -> 后端生成 6 位验证码，写入 email_verification_codes
  -> 后端发送邮件
  -> 用户输入验证码
  -> 前端请求 /api/auth/email/verify-code
  -> 后端校验验证码
  -> 不存在用户则创建 users
  -> 创建 user_sessions
  -> 设置 HttpOnly Cookie
  -> 返回当前用户信息
```

验证码规则建议：

- 6 位数字。
- 有效期 5 分钟。
- 同一邮箱 60 秒内只能发送一次。
- 同一邮箱 10 分钟内最多发送 5 次。
- 同一验证码最多尝试 5 次。
- 验证成功后立即置为已使用。
- 数据库只保存验证码哈希，不保存明文验证码。

### 3.2 Google 登录

Google 登录建议使用标准 OAuth 2.0 Authorization Code Flow。

```text
前端点击 Continue with Google
  -> 跳转 /api/auth/oauth/google/start
  -> 后端生成 state，保存到 Cookie 或 Redis
  -> 跳转 Google 授权页
  -> Google 回调 /api/auth/oauth/google/callback
  -> 后端校验 state
  -> 后端用 code 换 access_token / id_token
  -> 校验 id_token 签名与 aud
  -> 读取 email、sub、avatar
  -> 查找 oauth_accounts
  -> 没有则绑定或创建 users
  -> 创建 session
  -> 跳转前端 /auth/callback
```

Google 的用户唯一标识不要用邮箱作为唯一依据，应使用 `provider_user_id = sub`。邮箱可以变化，`sub` 更稳定。

### 3.3 微信登录

如果是网页端，通常是微信开放平台扫码登录。需要注意：微信登录在开发调试时比 Google 更麻烦，因为它依赖开放平台应用、回调域名备案或可信域名配置。

推荐放在第三阶段实现：

```text
前端点击微信登录
  -> 后端生成微信二维码登录 URL
  -> 用户扫码确认
  -> 微信回调 code
  -> 后端用 code 换 access_token
  -> 获取 openid / unionid
  -> 查找 oauth_accounts
  -> 绑定或创建 users
  -> 创建 session
```

如果项目只是本地演示，可以在文档中保留微信登录设计，实际代码先接 Google 和邮箱验证码。

### 3.4 人机验证

人机验证建议放在“发送验证码”之前，而不是登录成功之后。否则攻击者仍然可以滥发邮件。

可选方案：

- Cloudflare Turnstile：接入简单，用户体验较好。
- Google reCAPTCHA：生态成熟，但国内访问可能不稳定。
- hCaptcha：也可以用，但 UI 存在感更强。

推荐流程：

```text
前端加载 Turnstile 组件
  -> 用户完成验证
  -> 前端拿到 captcha_token
  -> 请求发送验证码时带上 captcha_token
  -> 后端请求 Turnstile verify API
  -> 通过后才发送邮件
```

开发环境可以通过配置关闭人机验证：

```env
AUTH_CAPTCHA_ENABLED=false
```

## 4. 数据库设计

现有 `users` 表字段太少，只适合占位。登录系统建议扩展用户表，并新增验证码、第三方账号、会话和审计日志表。

### 4.1 users 表调整

建议把 `username` 保留为展示名或兼容字段，新增 `email`、`status`、`avatar_url` 等字段。

```sql
ALTER TABLE users
  ADD COLUMN email VARCHAR(255) NULL UNIQUE AFTER username,
  ADD COLUMN display_name VARCHAR(100) NULL AFTER email,
  ADD COLUMN avatar_url VARCHAR(500) NULL AFTER display_name,
  ADD COLUMN status VARCHAR(32) NOT NULL DEFAULT 'active' AFTER role,
  ADD COLUMN last_login_at DATETIME NULL AFTER status;
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| email | 邮箱验证码登录的主账号 |
| display_name | 展示名，默认取邮箱前缀 |
| avatar_url | Google / 微信头像 |
| status | `active` / `disabled` |
| last_login_at | 最近登录时间 |

如果后续需要传统密码登录，再保留 `password_hash`；如果只做验证码和 OAuth，`password_hash` 可以长期为空。

### 4.2 email_verification_codes

保存邮箱验证码记录。

```sql
CREATE TABLE IF NOT EXISTS email_verification_codes (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  email VARCHAR(255) NOT NULL,
  code_hash VARCHAR(255) NOT NULL,
  purpose VARCHAR(32) NOT NULL DEFAULT 'login',
  expires_at DATETIME NOT NULL,
  used_at DATETIME NULL,
  attempt_count INT NOT NULL DEFAULT 0,
  send_ip VARCHAR(64) NULL,
  user_agent VARCHAR(500) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_email_codes_email_created (email, created_at),
  INDEX idx_email_codes_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

`code_hash` 建议使用：

```text
SHA256(email + ":" + code + ":" + AUTH_CODE_SECRET)
```

不要保存明文验证码。

### 4.3 oauth_accounts

保存第三方账号绑定关系。

```sql
CREATE TABLE IF NOT EXISTS oauth_accounts (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  provider VARCHAR(32) NOT NULL,
  provider_user_id VARCHAR(128) NOT NULL,
  email VARCHAR(255) NULL,
  nickname VARCHAR(100) NULL,
  avatar_url VARCHAR(500) NULL,
  raw_profile JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_oauth_provider_user (provider, provider_user_id),
  INDEX idx_oauth_user_id (user_id),
  CONSTRAINT fk_oauth_user_id
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

`provider` 取值：

```text
google
wechat
```

### 4.4 user_sessions

如果使用服务端会话，建议增加会话表。它比纯 JWT 更容易做退出登录、踢下线和安全审计。

```sql
CREATE TABLE IF NOT EXISTS user_sessions (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  session_id VARCHAR(128) NOT NULL UNIQUE,
  user_id BIGINT NOT NULL,
  refresh_token_hash VARCHAR(255) NULL,
  ip_address VARCHAR(64) NULL,
  user_agent VARCHAR(500) NULL,
  expires_at DATETIME NOT NULL,
  revoked_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_sessions_user_id (user_id),
  INDEX idx_sessions_expires (expires_at),
  CONSTRAINT fk_sessions_user_id
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 4.5 auth_audit_logs

记录登录、验证码发送、失败原因，方便排查问题。

```sql
CREATE TABLE IF NOT EXISTS auth_audit_logs (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NULL,
  email VARCHAR(255) NULL,
  action VARCHAR(64) NOT NULL,
  success BOOLEAN NOT NULL,
  ip_address VARCHAR(64) NULL,
  user_agent VARCHAR(500) NULL,
  detail VARCHAR(500) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_auth_logs_user_created (user_id, created_at),
  INDEX idx_auth_logs_email_created (email, created_at),
  INDEX idx_auth_logs_action_created (action, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

常见 `action`：

```text
email_code_requested
email_code_verified
email_code_failed
google_login
wechat_login
logout
captcha_failed
```

## 5. 后端模块设计

建议新增这些文件：

```text
backend/app/api/auth.py
backend/app/models/auth.py
backend/app/schemas/auth.py
backend/app/services/auth_service.py
backend/app/services/email_service.py
backend/app/services/oauth_service.py
backend/app/core/security.py
backend/app/core/auth_dependencies.py
```

### 5.1 配置项

在 `backend/app/core/config.py` 增加：

```python
auth_cookie_name: str = "mag2read_session"
auth_session_days: int = 14
auth_code_ttl_minutes: int = 5
auth_code_send_interval_seconds: int = 60
auth_code_secret: str = "change-me"

smtp_host: str | None = None
smtp_port: int = 465
smtp_user: str | None = None
smtp_password: str | None = None
smtp_from: str | None = None

google_client_id: str | None = None
google_client_secret: str | None = None
google_redirect_uri: str | None = None

wechat_app_id: str | None = None
wechat_app_secret: str | None = None
wechat_redirect_uri: str | None = None

auth_captcha_enabled: bool = False
turnstile_secret_key: str | None = None
```

`.env.example` 同步补充这些配置。

### 5.2 会话策略

推荐使用 HttpOnly Cookie 保存 `session_id`：

- 前端 JS 不能读取 Cookie，降低 XSS 窃取风险。
- 后端通过 Cookie 查询 `user_sessions`。
- 退出登录时可以直接撤销 session。

Cookie 建议：

```text
HttpOnly=true
SameSite=Lax
Secure=生产环境 true，本地开发 false
Path=/
Max-Age=14 天
```

如果前后端跨域部署，需要：

- FastAPI CORS `allow_credentials=True`。
- 前端 `fetch` 加 `credentials: "include"`。
- Cookie `SameSite=None; Secure`。

### 5.3 当前用户依赖

新增依赖：

```python
def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    session_id = request.cookies.get(settings.auth_cookie_name)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = auth_service.get_valid_session(db, session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    user = auth_service.get_user(db, session.user_id)
    if not user or user.status != "active":
        raise HTTPException(status_code=403, detail="User disabled")
    return user
```

对允许匿名访问的接口，可使用：

```python
def get_optional_user(...) -> User | None:
    ...
```

## 6. 接口设计

统一路径：

```text
/api/auth
```

### 6.1 发送邮箱验证码

```text
POST /api/auth/email/request-code
```

请求：

```json
{
  "email": "name@example.com",
  "captcha_token": "turnstile-token"
}
```

响应：

```json
{
  "message": "验证码已发送",
  "cooldown_seconds": 60
}
```

后端处理：

- 校验邮箱格式。
- 校验人机验证。
- 校验发送频率。
- 生成 6 位验证码。
- 写入 `email_verification_codes`。
- 发送邮件。
- 写入 `auth_audit_logs`。

### 6.2 校验验证码并登录

```text
POST /api/auth/email/verify-code
```

请求：

```json
{
  "email": "name@example.com",
  "code": "123456"
}
```

响应：

```json
{
  "user": {
    "id": 12,
    "email": "name@example.com",
    "display_name": "name",
    "avatar_url": null,
    "role": "user"
  }
}
```

后端处理：

- 查询最近一条未使用、未过期验证码。
- 比对验证码哈希。
- 失败则增加 `attempt_count`。
- 成功则创建或更新用户。
- 写入 `used_at`。
- 创建 `user_sessions`。
- 设置 Cookie。

### 6.3 获取当前用户

```text
GET /api/auth/me
```

响应：

```json
{
  "id": 12,
  "email": "name@example.com",
  "display_name": "name",
  "avatar_url": null,
  "role": "user"
}
```

未登录返回：

```text
401 Not authenticated
```

### 6.4 退出登录

```text
POST /api/auth/logout
```

处理：

- 后端根据 Cookie 找到 session。
- 设置 `revoked_at`。
- 清除 Cookie。

### 6.5 Google 登录

```text
GET /api/auth/oauth/google/start
GET /api/auth/oauth/google/callback
```

`start` 不返回 JSON，直接重定向 Google 授权页。

`callback` 成功后重定向：

```text
http://localhost:5173/auth/callback?provider=google&status=success
```

失败后重定向：

```text
http://localhost:5173/login?error=google_login_failed
```

### 6.6 微信登录

```text
GET /api/auth/oauth/wechat/start
GET /api/auth/oauth/wechat/callback
```

本地开发阶段可以先返回“未配置微信登录”，避免前端按钮点了没有反馈：

```json
{
  "message": "微信登录暂未配置"
}
```

## 7. 现有任务接口需要改什么

### 7.1 上传任务绑定用户

当前 `upload_task_file` 没有用户依赖。建议改为：

```python
async def upload_task_file(
    ...,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ...
    TaskCreate(
        task_id=task_id,
        original_name=original_name,
        input_type=input_type,
        output_format=output_format,
        user_id=current_user.id,
    )
```

对应 `TaskCreate` schema 需要允许内部传入 `user_id`，或者在 service 层单独设置。

### 7.2 任务列表只返回自己的任务

当前：

```python
task_service.list_tasks(db, limit=limit, offset=offset)
```

改为：

```python
task_service.list_tasks(db, user_id=current_user.id, limit=limit, offset=offset)
```

SQLAlchemy 查询增加：

```python
.filter(Task.user_id == user_id)
```

### 7.3 任务详情校验归属

`ensure_task` 建议改为：

```python
def ensure_user_task(db: Session, task_id: str, current_user: User):
    task = task_service.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No permission")
    return task
```

所有 `/api/tasks/{task_id}`、导出下载、页面预览、WebSocket 任务事件都需要用同一套归属校验。

## 8. 前端界面设计

参考图的优点是：登录表单很安静，左侧完成登录任务，右侧展示产品能力，但右侧视觉被弱化，不抢操作焦点。Mag2Read 可以沿用这个结构。

### 8.1 页面结构

```text
登录页 /login

左侧：登录表单
  Mag2Read Logo
  标题：登录 Mag2Read
  说明：用邮箱验证码继续，无需设置密码
  邮箱输入框
  继续按钮
  验证码输入框
  登录按钮
  分割线
  Google 登录
  微信登录
  协议说明

右侧：产品预览
  使用当前首页 hero 插画或上传流程示意图
  三个淡化能力点：版面分析 / OCR / 多格式导出
```

### 8.2 交互状态

邮箱阶段：

- 输入邮箱。
- 点击“继续”。
- 按钮 loading。
- 成功后进入验证码阶段。

验证码阶段：

- 显示“验证码已发送至 name@example.com”。
- 6 位验证码输入框。
- 倒计时 60 秒。
- “重新发送验证码”倒计时结束后可点。
- 登录成功后跳回来源页，默认上传页。

错误处理：

| 场景 | 前端提示 |
| --- | --- |
| 邮箱格式错误 | 请输入有效邮箱 |
| 发送太频繁 | 请稍后再试 |
| 验证码错误 | 验证码不正确或已过期 |
| 人机验证失败 | 请完成人机验证 |
| 第三方登录失败 | 登录失败，请重新尝试 |

### 8.3 前端状态管理

建议新增：

```text
UI/src/auth/AuthContext.tsx
UI/src/auth/LoginPage.tsx
UI/src/auth/authApi.ts
UI/src/auth/RequireAuth.tsx
```

`AuthContext` 保存：

```ts
type AuthUser = {
  id: number;
  email: string;
  display_name: string;
  avatar_url: string | null;
  role: "user" | "admin";
};
```

初始化时请求：

```text
GET /api/auth/me
```

如果返回 200，说明已登录；如果 401，说明游客状态。

### 8.4 Header 调整

首页右上角：

- 未登录：`登录`、`免费开始`
- 已登录：用户头像/邮箱前缀、退出登录

点击“免费开始”：

- 未登录：跳到 `/login?redirect=/upload`
- 已登录：进入上传界面

上传接口如果返回 401：

- 前端跳到登录页。
- 登录成功后回到上传界面。

## 9. 邮件模板

邮件标题：

```text
Mag2Read 登录验证码
```

邮件正文：

```text
你正在登录 Mag2Read。

验证码：123456

验证码 5 分钟内有效。如果不是你本人操作，可以忽略这封邮件。
```

HTML 邮件可以做得更精致，但不要影响主流程。课程项目里，纯文本邮件更容易调试。

## 10. 安全细节

必须做：

- 验证码不存明文。
- 验证码有过期时间。
- 验证码有尝试次数限制。
- 发送验证码有频率限制。
- 登录态 Cookie 使用 HttpOnly。
- 任务接口校验用户归属。
- OAuth 回调校验 `state`。
- Google 登录校验 `id_token` 的 `aud`。
- 生产环境 Cookie 开启 `Secure`。

建议做：

- 对发送验证码接口加人机验证。
- 对登录失败写入审计日志。
- 记录 IP 和 User-Agent。
- 定期清理过期验证码和过期 session。
- 管理员可以查看用户任务，但普通用户不能互相访问任务。

## 11. 开发步骤

### 第一步：数据库迁移

1. 扩展 `users` 表。
2. 新增 `email_verification_codes`。
3. 新增 `user_sessions`。
4. 新增 `oauth_accounts`。
5. 新增 `auth_audit_logs`。

建议把 SQL 写到：

```text
backend/database/auth_migration.sql
```

### 第二步：后端基础认证

1. 新增 `backend/app/models/auth.py` 或扩展现有模型。
2. 新增 `backend/app/schemas/auth.py`。
3. 新增 `backend/app/core/security.py`，放验证码哈希、session 生成、Cookie 设置工具。
4. 新增 `backend/app/services/email_service.py`。
5. 新增 `backend/app/services/auth_service.py`。
6. 新增 `backend/app/api/auth.py`。
7. 在 `main.py` 中注册 auth router。

### 第三步：接入任务归属

1. 上传任务写入 `user_id`。
2. 任务列表按当前用户过滤。
3. 任务详情、文件、页面、导出下载校验用户归属。
4. WebSocket 连接时校验当前用户是否有权访问该任务。

### 第四步：前端登录页

1. 新增登录页 UI。
2. 新增邮箱验证码交互。
3. 新增 `AuthContext`。
4. Header 根据登录态展示不同按钮。
5. 上传前检查登录态。

### 第五步：Google 登录

1. Google Cloud Console 创建 OAuth Client。
2. 配置回调地址。
3. 实现 `/api/auth/oauth/google/start`。
4. 实现 `/api/auth/oauth/google/callback`。
5. 前端增加 Google 登录按钮跳转。

### 第六步：人机验证

1. 创建 Turnstile site key / secret key。
2. 前端登录页加载 Turnstile。
3. 发送验证码时提交 `captcha_token`。
4. 后端校验 token。
5. 开发环境允许关闭。

### 第七步：微信登录

1. 准备微信开放平台应用。
2. 配置回调域名。
3. 实现微信扫码登录。
4. 把 `unionid/openid` 写入 `oauth_accounts`。

## 12. 验收清单

邮箱验证码：

- 输入合法邮箱可以收到验证码。
- 60 秒内不能重复发送。
- 错误验证码不能登录。
- 过期验证码不能登录。
- 登录成功后刷新页面仍保持登录。
- 退出登录后访问 `/api/auth/me` 返回 401。

任务隔离：

- 用户 A 看不到用户 B 的任务列表。
- 用户 A 不能访问用户 B 的任务详情。
- 用户 A 不能下载用户 B 的导出文件。
- 未登录上传返回 401。

第三方登录：

- Google 登录能创建用户。
- 同一个 Google 账号再次登录不会重复创建用户。
- OAuth state 不匹配时登录失败。

安全：

- Cookie 是 HttpOnly。
- 验证码表中没有明文验证码。
- 登录失败有审计日志。
- 人机验证失败时不发送邮件。

## 13. 推荐优先级

最适合课程项目展示的版本：

```text
必做：
  邮箱验证码登录注册
  登录态 Cookie
  任务归属隔离
  登录页 UI

加分：
  Google 登录
  人机验证
  登录审计日志

可选：
  微信扫码登录
  管理员用户管理页
```

如果时间有限，先不要做微信登录。微信登录的难点更多在平台配置和回调域名，不一定能充分体现后端设计能力。邮箱验证码 + Google 登录 + 人机验证 + 任务隔离，已经能形成比较完整的认证系统闭环。
