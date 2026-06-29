# Unseen Studio 风格开发计划

> 项目名称：Mag2Read PDF 文档转换系统  
> 运行环境：前端 npm（Node.js 25.2.1），后端 conda env `industrial-cv`（Python 3.10.20）  
> 目标：在现有功能完整的基础上，引入 Unseen Studio 风格的视觉品质提升

---

## 总体策略

本计划按照 **投入产出比从高到低** 排列阶段，每个阶段可独立交付，不阻塞后续阶段。

```
阶段 1: 微交互打磨（CSS + 少量 JS） → 立竿见影
阶段 2: Framer Motion 页面过渡 → 结构清晰
阶段 3: Three.js 微背景 → 沉浸感升级
阶段 4: 管道进度可视化增强 → 核心流程视觉重设计
阶段 5: 3D 文档结构预览 → 亮点功能
```

---

## 阶段 1：微交互打磨

### 1.1 上传区域拖拽边框动画

**目标**：拖拽文件到上传区时，边框产生流动光效

**技术方案**：纯 CSS，利用 `@property` 注册自定义属性 + `conic-gradient` 实现边框旋转动画

**实现位置**：`UI/src/styles.css`，`.upload-card` 的 drag-over 状态

**关键代码思路**：
```css
@property --border-angle {
  syntax: "<angle>";
  inherits: false;
  initial-value: 0deg;
}

.upload-card.drag-over {
  --border-angle: 360deg;
  border-image: conic-gradient(
    from var(--border-angle),
    transparent 0deg,
    #3084ff 60deg,
    transparent 120deg
  ) 1;
  animation: border-spin 2s linear infinite;
}

@keyframes border-spin {
  to { --border-angle: 360deg; }
}
```

### 1.2 阶段完成动画

**目标**：每个处理阶段完成时，指示灯弹跳 + 光晕

**实现位置**：`UI/src/styles.css`，`.stage-node.completed`

```css
.stage-node.completed {
  animation: stage-pop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes stage-pop {
  0% { transform: scale(1); }
  50% { transform: scale(1.25); }
  100% { transform: scale(1); }
}
```

### 1.3 导出按钮 Shimmer 光效

**目标**：主要导出按钮悬停时有扫光效果

**实现位置**：`UI/src/styles.css`，`.export-button`

```css
.export-button.shimmer::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(
    105deg,
    transparent 30%,
    rgba(255,255,255,0.4) 50%,
    transparent 70%
  );
  background-size: 200% 100%;
  animation: shimmer 2.5s ease-in-out infinite;
}

@keyframes shimmer {
  from { background-position: 200% 0; }
  to { background-position: -200% 0; }
}
```

### 1.4 数字递增计数动画

**目标**：完成页面的指标数字从 0 递增到最终值

**实现位置**：新建 `UI/src/hooks/useCountUp.ts` + `UI/src/components/CountUp.tsx`

**技术方案**：`requestAnimationFrame` 驱动，时长 1.2s，ease-out

```tsx
// 伪代码
function useCountUp(end: number, duration = 1200) {
  const [value, set] = useState(0);
  useEffect(() => {
    // requestAnimationFrame 驱动从 0 → end 的插值
  }, [end]);
  return value;
}
```

### 1.5 prefers-reduced-motion 尊重

确保所有动画在用户开启「减少运动」时关闭：

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 阶段 2：Framer Motion 页面过渡

### 2.1 安装依赖

```bash
npm install framer-motion
```

### 2.2 改造 App.tsx 视图切换

**当前结构**：三个视图通过 `mode` 状态条件渲染，切换是瞬发的

**改造目标**：使用 `<AnimatePresence mode="wait">` + `<motion.div>` 实现：

- 视图退出时：透明度 0 + 向下位移 20px + 轻微缩放 (0.98)
- 视图进入时：透明度 1 + 向上位移 0 + 缩放 1
- 共用 0.35s `easeInOut`，交错 0.08s

**实现位置**：`UI/src/App.tsx`

```tsx
import { motion, AnimatePresence } from "framer-motion";

const pageVariants = {
  initial: { opacity: 0, y: 20, scale: 0.98 },
  animate: { opacity: 1, y: 0, scale: 1 },
  exit: { opacity: 0, y: -10, scale: 0.97 }
};

// 在 render 中用 AnimatePresence 包裹每个视图
```

### 2.3 列表条目交错动画

处理阶段列表、导出文件列表使用 `staggerChildren` 实现依次出现。

---

## 阶段 3：Three.js 微背景

### 3.1 安装依赖

```bash
npm install three @react-three/fiber @react-three/drei
```

### 3.2 创建 FluidBackground 组件

**新建文件**：`UI/src/components/FluidBackground.tsx`

**实现方案**：使用 `@react-three/fiber` 的 Canvas + 自定义着色器 Material，渲染一个全屏流体渐变背景

**技术要点**：
- `position: fixed`，`z-index: -1`，`pointer-events: none`
- 使用 `window.devicePixelRatio` 控制分辨率
- 着色器用 `noise` 函数驱动颜色缓慢变化
- 鼠标移动影响流体方向

### 3.3 性能考量

- 默认帧率：30fps（降低功耗）
- 移动端自动降级为静态渐变（通过 `useMediaQuery` 或设备检测）
- Canvas 不会遮挡任何交互元素

---

## 阶段 4：管道进度可视化增强

### 4.1 改造 stage-node 为管道式流程

**目标**：将现有的阶段指示器从静态列表改为视觉上连贯的管道

**具体实现**：
- 水平布局（大屏） / 垂直布局（小屏）
- 每个阶段是一个圆形节点
- 节点之间有连接线，已完成和进行中的连接线有渐变流动效果
- 当前活跃节点有呼吸脉冲光晕

### 4.2 数据驱动的实时进度条

**目标**：利用后端返回的 `progress` 字段，在管道下方显示实时进度

- 进度条使用渐变色，左侧已完成部分呈蓝色渐变
- 右侧未完成部分为浅灰
- 进度条上方显示当前阶段的描述文字

---

## 阶段 5：3D 文档结构预览

### 5.1 功能位置

在 `task-screen` 的 `explain-stage` 中增加一个切换按钮 "3D 结构"，点击后展开 Three.js 场景

### 5.2 数据来源

使用后端返回的 `ExplainPageData[]` 中的 `blocks` 数组，每个 block 包含：
- `bbox`（x1, y1, x2, y2）
- `type`（heading / paragraph / image / table / noise）
- `ocr_confidence`

### 5.3 3D 场景设计

- 按页分排，每页在 Z 轴上偏移 2 个单位
- 每个 block 根据 `bbox` 生成平面几何体
- 颜色映射：heading = 蓝色、paragraph = 白色、image = 绿色、table = 橙色、noise = 红色
- 透明度映射：透明度 = 1 - `ocr_confidence`（置信度越低越透明）
- OrbitControls 允许用户旋转/缩放
- 选中的 block 高亮并显示信息标签

### 5.4 新建文件

- `UI/src/components/Doc3DPreview.tsx`
- 包含 `Canvas`、`BlocksMesh`、`DocControls` 子组件

---

## 目录结构变化

```
UI/src/
├── App.tsx                    # 修改：添加 Framer Motion 过渡
├── main.tsx                   # 不变
├── styles.css                 # 修改：添加微交互 + 管道动画样式
├── components/
│   ├── FluidBackground.tsx    # 新增：Three.js 流体背景
│   ├── Doc3DPreview.tsx       # 新增：3D 文档结构预览
│   ├── CountUp.tsx            # 新增：数字递增动画
│   └── PipelineFlow.tsx       # 新增：管道进度可视化
└── hooks/
    └── useCountUp.ts          # 新增：计数动画 hook
```

---

## 安装命令汇总

```bash
# 在 UI 目录下执行
cd /Users/zhu/projects/python-project/课程项目2/UI
npm install framer-motion three @react-three/fiber @react-three/drei
```

---

## 验证方式

```bash
# 启动前端
cd /Users/zhu/projects/python-project/课程项目2/UI
npm run dev

# 浏览器访问 http://localhost:5173
# 1. 观察上传区拖拽动画
# 2. 点击上传开始转换，观察页面过渡和管道动画
# 3. 观察完成页面的计数动画
# 4. 点击 "3D 结构" 按钮查看文档结构
```
