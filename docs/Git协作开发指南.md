 # Mag2Read 项目 Git 协作开发指南
 
 **仓库地址：** https://github.com/zhushanv/mag2read
 
 ---
 
 ## 一、项目结构与仓库概览
 
 在开始协作之前，先弄清楚项目的整体结构。Mag2Read 是一个前后端分离的项目，仓库下主要包含两个工作目录：
 
 ```
 mag2read/
 ├── UI/                    # 前端 — React + Vite + TypeScript
 │   ├── src/
 │   │   ├── components/    # 页面组件（Doc3DPreview, FluidBackground 等）
 │   │   ├── App.tsx        # 根组件
 │   │   └── main.tsx       # 入口文件
 │   ├── package.json
 │   └── vite.config.ts
 ├── backend/               # 后端 — FastAPI + PaddleOCR + Celery
 │   ├── app/
 │   │   ├── api/           # 路由层（tasks, auth, exports, health）
 │   │   ├── services/      # 业务逻辑（task_service, auth_service）
 │   │   ├── models/        # 数据模型
 │   │   ├── schemas/       # Pydantic 数据校验
 │   │   └── main.py        # FastAPI 应用入口
 │   ├── database/          # SQL 初始化脚本
 │   └── scripts/           # 独立脚本（OCR、布局分析、导出等）
 ├── docs/                  # 开发文档
 └── environment.yml        # conda 环境配置
 ```
 
 > 💡 你们团队可以按模块分工——比如一个人负责前端 UI，另一个人负责后端 API 和服务层。分支命名也建议按模块来，后面会讲到。
 
 ---
 
 ## 二、环境准备（每人只需做一次）
 
 ### 2.1 安装 Git
 
 macOS 用户一般自带 Git，在终端输入 `git --version` 确认。Windows 用户去 https://git-scm.com 下载安装。
 
 ### 2.2 配置用户信息
 
 Git 需要知道你是谁，每次提交都会记录你的名字和邮箱：
 
 ```bash
 git config --global user.name "你的名字"
 git config --global user.email "你的邮箱@example.com"
 
 # 建议再配置一下默认分支名为 main
 git config --global init.defaultBranch main
 ```
 
 > 💡 名字和邮箱最好跟你的 GitHub 账号一致，这样提交记录才能正确关联到你的 GitHub 头像。
 
 ### 2.3 配置 SSH 密钥
 
 用 SSH 方式和 GitHub 通信，免去每次输入密码的麻烦：
 
 ```bash
 # 1. 生成 SSH 密钥
 ssh-keygen -t ed25519 -C "你的邮箱@example.com"
 # 一路回车即可（默认保存在 ~/.ssh/id_ed25519）
 
 # 2. 启动 ssh-agent 并添加密钥
 eval "$(ssh-agent -s)"
 ssh-add ~/.ssh/id_ed25519
 
 # 3. 复制公钥到剪贴板
 cat ~/.ssh/id_ed25519.pub
 # 将输出的内容完整复制
 ```
 
 然后打开 GitHub → Settings → SSH and GPG keys → New SSH key，把公钥粘贴进去。完成后验证：
 
 ```bash
 ssh -T git@github.com
 # 看到 "Hi xxx! You've successfully authenticated" 就说明配置好了
 ```
 
 ### 2.4 克隆仓库
 
 每位协作者在自己的电脑上克隆项目：
 
 ```bash
 git clone git@github.com:zhushanv/mag2read.git
 cd mag2read
 ```
 
 > 💡 一定要用 SSH 地址（`git@...`），不要用 HTTPS 地址，否则后续推送可能频繁要求输密码。
 
 ---
 
 ## 三、分支策略——我们的协作规则
 
 多人同时在一个分支上改代码，迟早会互相覆盖。分支的核心思想很简单：**每个人在自己的分支上干活，干完了再合并到主分支。**
 
 ### 3.1 分支命名约定
 
 | 分支类型 | 命名格式 | 示例 | 说明 |
 |---------|---------|------|------|
 | 主分支 | `main` | `main` | 始终可部署的稳定代码 |
 | 前端功能 | `feat/ui-xxx` | `feat/ui-result-page` | 前端新功能或页面 |
 | 后端功能 | `feat/api-xxx` | `feat/api-export-doc` | 后端新接口或服务 |
 | 修复 | `fix/xxx` | `fix/ocr-crash` | Bug 修复 |
 | 文档 | `docs/xxx` | `docs/api-guide` | 文档更新 |
 | 重构 | `refactor/xxx` | `refactor/task-service` | 代码重构，不改功能 |
 
 ### 3.2 核心原则
 
 - **main 分支永远不要直接提交代码**，所有改动都通过分支 + Pull Request 进入。
 - 每次开始新任务之前，先从最新的 main 拉出新分支。
 - 一个分支只做一件事——不要在 `feat/ui-login` 分支里顺手改了后端导出逻辑。
 - 分支名要有意义，看到名字就知道这个分支在做什么。
 - 功能开发完成后，通过 Pull Request（PR）合并到 main，不要自己直接 merge。
 
 ---
 
 ## 四、日常开发流程（手把手）
 
 下面是每一次开发任务的完整流程，按顺序执行即可。
 
 ### 步骤一：同步最新代码
 
 开始工作前，先把远程仓库的最新代码拉到本地：
 
 ```bash
 git checkout main
 git pull origin main
 ```
 
 > 💡 养成习惯——每次动手写代码之前都先 pull 一下，避免在旧代码基础上开发。
 
 ### 步骤二：创建功能分支
 
 基于最新的 main 创建你自己的分支：
 
 ```bash
 # 例如你要开发前端的结果页面
 git checkout -b feat/ui-result-page
 ```
 
 这条命令做了两件事：切换到新分支 `feat/ui-result-page`，并且这个分支的起点就是当前 main 的最新状态。
 
 ### 步骤三：编写代码并提交
 
 正常写代码就行。改了一部分之后可以随时提交：
 
 ```bash
 # 查看改了哪些文件
 git status
 
 # 添加想要提交的文件
 git add UI/src/components/ResultPage.tsx
 # 或者一次性添加所有改动
 git add .
 
 # 提交，写清楚你做了什么
 git commit -m "feat: 添加结果页面基础布局"
 ```
 
 提交信息（commit message）的写法建议遵循以下格式：
 
 | 前缀 | 用途 | 示例 |
 |------|------|------|
 | `feat:` | 新功能 | `feat: 添加用户注册接口` |
 | `fix:` | 修复 Bug | `fix: 修复 PDF 导出乱码问题` |
 | `docs:` | 文档更新 | `docs: 补充 API 接口说明` |
 | `style:` | 代码格式调整（不影响逻辑） | `style: 统一缩进为 2 空格` |
 | `refactor:` | 重构 | `refactor: 拆分 task_service 方法` |
 | `chore:` | 杂项（依赖更新、配置调整等） | `chore: 升级 vite 到 5.4` |
 
 > 💡 提交要勤快、粒度要小。不要写了一天代码才提交一次，那样出了问题很难定位。每完成一个小功能点就提交一次。
 
 ### 步骤四：推送到远程仓库
 
 ```bash
 # 第一次推送新分支时，设置上游分支
 git push -u origin feat/ui-result-page
 
 # 后续推送只需要
 git push
 ```
 
 ### 步骤五：创建 Pull Request
 
 代码推送到 GitHub 后，打开浏览器：
 
 1. 进入 https://github.com/zhushanv/mag2read
 2. GitHub 会自动提示你刚推送了新分支，点击 **"Compare & pull request"**
 3. 填写 PR 标题和描述，说明你做了什么、怎么测试的
 4. 在右侧 **Reviewers** 栏指定一位同学来审查你的代码
 5. 点击 **"Create pull request"**
 
 ### 步骤六：代码审查与合并
 
 被指定审查的同学需要：
 
 1. 打开 PR 页面，阅读代码改动
 2. 如果有问题，在对应代码行留评论（Comment），或请求修改（Request changes）
 3. 如果没问题，点击 **Approve**
 4. 确认通过后，由项目负责人点击 **"Merge pull request"** 完成合并
 
 > 💡 合并完成后，GitHub 会提示是否删除该分支。点删除即可——分支的使命已经完成了，本地也可以用 `git branch -d feat/ui-result-page` 清理。
 
 ### 步骤七：同步到本地
 
 PR 合并后，你本地 main 还是旧的，需要同步：
 
 ```bash
 git checkout main
 git pull origin main
 ```
 
 ---
 
 ## 五、处理冲突——不用慌
 
 两个人改了同一个文件的同一个地方，Git 就没法自动合并了，这就是**冲突**。冲突不丢代码，只是需要你手动决定保留哪部分。
 
 ### 5.1 什么时候会遇到冲突
 
 典型场景：你在 `feat/ui-login` 分支改了 `App.tsx`，你的同学在 `feat/api-auth` 分支也改了 `App.tsx`。他的 PR 先合并了，你推送时就会提示冲突。
 
 ### 5.2 解决步骤
 
 ```bash
 # 1. 把最新的 main 合并到你的分支
 git checkout feat/ui-login
 git fetch origin
 git merge origin/main
 
 # 2. Git 会提示哪些文件冲突了
 # 打开冲突文件，会看到类似这样的标记：
 # <<<<<<< HEAD
 # 你的代码
 # =======
 # 别人的代码
 # >>>>>>> origin/main
 
 # 3. 手动编辑，保留你需要的内容，删除标记
 
 # 4. 标记冲突已解决
 git add <冲突的文件>
 
 # 5. 完成合并
 git commit -m "merge: 解决与 main 的冲突"
 
 # 6. 推送
 git push
 ```
 
 > ⚠️ 解决冲突时不要慌，仔细看两边代码分别改了什么，根据实际情况决定保留哪边或两边都保留。如果拿不准，直接问写那段代码的同学。
 
 ---
 
 ## 六、常用命令速查
 
 | 场景 | 命令 |
 |------|------|
 | 查看当前分支 | `git branch` |
 | 切换分支 | `git checkout <分支名>` |
 | 查看文件改动 | `git diff` |
 | 查看提交历史 | `git log --oneline -10` |
 | 撤销工作区修改（未 add） | `git checkout -- <文件>` |
 | 撤销暂存（已 add，未 commit） | `git reset HEAD <文件>` |
 | 修改最近一次提交信息 | `git commit --amend -m "新信息"` |
 | 拉取远程更新但不合并 | `git fetch origin` |
 | 查看远程分支列表 | `git branch -r` |
 | 删除本地已合并的分支 | `git branch -d <分支名>` |
 | 删除远程分支 | `git push origin --delete <分支名>` |
 
 ---
 
 ## 七、分工建议与协作约定
 
 针对 Mag2Read 项目的前后端结构，给一些分工思路供参考：
 
 | 角色 | 负责模块 | 典型分支 | 注意点 |
 |------|---------|---------|--------|
 | 前端开发 A | UI 组件、页面交互 | `feat/ui-xxx` | 组件命名统一，样式文件放 src/ 下 |
 | 前端开发 B | 3D 预览、动画效果 | `feat/ui-3d-xxx` | Three.js 依赖已锁定版本，不要随意升级 |
 | 后端开发 A | API 路由、业务逻辑 | `feat/api-xxx` | 新增接口在 api/ 下新建文件 |
 | 后端开发 B | OCR Pipeline、Worker | `feat/ocr-xxx` | 修改 Pipeline 逻辑要跑 scripts/ 下的测试 |
 | 全栈/联调 | 前后端联调、部署 | `feat/integrate-xxx` | 联调时确保 vite proxy 指向后端端口 |
 
 ### 协作约定
 
 - 每天开始写代码前，先 `git pull origin main` 同步最新代码。
 - 提交前确保代码能正常运行——至少不要提交语法错误。
 - PR 描述要写清楚：做了什么、涉及哪些文件、如何测试。
 - 审查代码要认真看，不要无脑 Approve。
 - 合并后及时删除已合并的分支，保持分支列表干净。
 - 遇到问题及时在群里沟通，不要一个人卡很久。
 
 ---
 
 ## 八、完整示例——从开发到合并
 
 假设你要给项目添加一个文档导出接口，完整流程如下：
 
 ```bash
 # 1. 同步最新代码
 git checkout main
 git pull origin main
 
 # 2. 创建功能分支
 git checkout -b feat/api-export-doc
 
 # 3. 开发（在 backend/app/api/ 下新建 exports.py 等）
 # ... 写代码 ...
 
 # 4. 查看改动
 git status
 git diff
 
 # 5. 提交
 git add backend/app/api/exports.py backend/app/services/export_service.py
 git commit -m "feat: 添加文档导出接口，支持 PDF 和 Markdown 格式"
 
 # 6. 推送
 git push -u origin feat/api-export-doc
 
 # 7. 在 GitHub 上创建 Pull Request，指定审查人
 
 # 8. 审查通过后合并，删除远程分支
 
 # 9. 同步本地
 git checkout main
 git pull origin main
 git branch -d feat/api-export-doc
 ```
 
 ---
 
 ## 九、常见问题
 
 **Q：推送被拒绝（rejected）怎么办？**
 
 A：说明远程分支有你本地没有的提交。先 `git pull origin <分支名>` 合并远程改动，解决冲突后再推送。
 
 **Q：误提交了不该提交的文件怎么办？**
 
 A：如果还没推送：`git reset HEAD~1` 撤销最近一次提交（代码还在工作区）。如果已经推送了：用 `git revert` 生成一个反向提交。
 
 **Q：怎么查看某次提交改了什么？**
 
 A：`git show <提交哈希>` 可以看到那次提交的完整改动。
 
 **Q：如何同时开发多个功能？**
 
 A：每个功能一个分支，用 `git checkout` 在分支间切换。如果当前分支工作没做完又不想提交，用 `git stash` 暂存。
 
 **Q：合并时产生大量冲突怎么办？**
 
 A：说明你的分支和 main 分叉太久没同步。建议在开发过程中定期执行 `git merge origin/main` 保持分支更新，不要等到最后才合并。
 
 ---
 
 *本文档基于 Mag2Read 项目实际仓库结构编写，供团队协作参考。*
