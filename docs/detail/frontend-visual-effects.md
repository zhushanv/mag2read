# 前端视觉效果实现说明

本文记录 `UI/src` 里这次视觉优化的主要实现方式，后续如果需要调整风格，可以优先从这里对应到代码位置。

## 1. 液态光带背景

实现文件：`UI/src/components/FluidBackground.tsx`

背景使用 `@react-three/fiber` 渲染一个全屏 `Canvas`，核心效果来自自定义 fragment shader。页面上看到的液态光带不是图片，而是 shader 根据时间、鼠标位置和噪声函数实时计算出来的颜色。

关键变量：

- `uTime`：时间。`useFrame` 每帧更新它，shader 里用它推动光带移动。
- `uMouse`：鼠标位置。鼠标移动后会轻微改变背景流动方向。
- `uResolution` 和 `uDpr`：用于保证不同屏幕尺寸、不同像素密度下的背景比例稳定。

shader 里主要做了三件事：

1. 用 `noise()` 生成柔和的底色变化，避免背景是一张平铺渐变。
2. 用 `sin()` 叠加几条弯曲光带，例如 `ribbonA`、`ribbonB`、`ribbonC`。
3. 用 `mix()` 在蓝、青、暖橙、白色之间混色，形成类似液态折射的色彩层次。

如果想让背景流动更明显，可以调这些值：

- 速度：`float t = uTime * 0.26;`，数值越大越快。
- 摆动幅度：`0.32 * sin(...)`、`0.34 * sin(...)`，数值越大光带弯曲越明显。
- 透明度：`float alpha = ...`，整体数值越大背景越强。

## 2. 上传区玻璃面板

实现文件：`UI/src/UploadCard.tsx`、`UI/src/styles.css`

上传卡片本质是一个 `<label>`，里面有一个透明的 `<input type="file">` 覆盖整张卡片。这样用户点击卡片任意位置，包括视觉上的“点击上传”按钮，都能打开文件选择窗口。

玻璃质感主要来自四层：

- `.upload-form::before`：卡片背后的彩色光带。没有这层，`backdrop-filter` 就没有明显可模糊的内容。
- `.upload-card`：半透明底色、内阴影、外阴影和 `backdrop-filter`。
- `.upload-card::before`：细边缘高光，用 mask 做出只显示边框的效果。
- `.upload-card::after`：斜向扫光，高光在 hover 和 drag-over 时发生位移。

拖拽文件时，`.upload-card.drag-over` 会启用 `conic-gradient` 边框和 `glassBorderSpin` 动画，形成流动边缘光。

可调参数：

- 玻璃模糊强度：`.upload-card` 的 `backdrop-filter: blur(30px)`。
- 卡片高度：`.upload-card` 的 `min-height`。
- 拖拽流光速度：`.upload-card.drag-over` 的 `animation: glassBorderSpin 2.2s`。

## 3. 玻璃按钮系统

实现文件：`UI/src/styles.css`

以下按钮共用一套玻璃按钮基底：

- `.ghost-button`
- `.primary-button`
- `.secondary-button`
- `.format-pill`
- `.export-button`
- `.icon-button`
- `.back-button`

通用结构是：

1. 按钮本身使用半透明渐变、内阴影、外阴影、`backdrop-filter`。
2. `::after` 作为 hover 扫光层。
3. 主按钮和选中态按钮额外叠加蓝色渐变，保持主要操作的识别度。

如果按钮看起来太亮，可以降低背景里的 `rgba(255, 255, 255, ...)` 透明度；如果太平，可以加大 `box-shadow` 里的内阴影和外阴影。

## 4. 首页首屏比例

实现文件：`UI/src/styles.css`

为了让用户打开页面后能看到上传区、格式选择、高级选项和开始按钮，首页做了压缩：

- `.topbar` 高度从原来的大尺寸压到 `58px`。
- `.home-screen` 上下 padding 减少。
- `.headline h1` 字号降低，副标题间距减少。
- `.upload-card` 高度减少，图标尺寸同步缩小。
- `.upload-form` gap 减少。

历史记录仍保留下方，不强求首屏完整展示。

## 5. 处理页等待体验

实现文件：`UI/src/App.tsx`、`UI/src/styles.css`

处理页现在按“用户等待时最关心什么”重新排布：

- 顶部流程从大面积进度区变成 `.compact-progress`，只保留当前阶段、百分比进度和小流程节点。
- 左侧 `PreviewPane` 专注展示原文页面和识别框，去掉了“处理中产物”列表。
- 右侧 `TextPane` 改为“阅读稿预览”，清洗结果未生成时显示 `WaitingReadingPreview`。
- `WaitingReadingPreview` 使用扫描线和骨架行表达“正在整理”，不再直接暴露数据库写入、步骤 summary、JSON 等内部过程。

如果希望进一步降低流程标识占地，可以继续缩小 `.compact-progress .pipeline-icon` 和 `.compact-progress .pipeline-label`，或者只保留当前阶段与进度条。

## 6. 减少运动

实现文件：`UI/src/styles.css`

文件底部有 `@media (prefers-reduced-motion: reduce)`，会大幅降低动画持续时间和循环次数。新增动画应尽量放在同一个媒体查询控制范围内，避免用户开启系统“减少动态效果”后仍持续播放明显动画。
