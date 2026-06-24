Scholar Studio 桌面应用采用基于 **CSS 自定义属性（Design Tokens）** 的手写样式系统，未引入 Tailwind CSS、Bootstrap 或 Material UI 等第三方组件库。整体视觉风格定义为“Discourse Dark Theme”，强调深色背景下的学术沉浸感与高对比度阅读体验。

### 1. 核心设计系统 (Design Tokens)
所有样式变量统一定义在 `desktop/src/App.css` 的 `:root` 中，涵盖以下维度：
- **色彩体系**：
  - 背景色：以深灰褐色为主基调 (`--bg-base: #3F3D3C`, `--bg-elevated: #464443`)，辅以半透明表面层 (`--bg-surface`)。
  - 文本色：米白色主文本 (`--text-primary: #FBF7EF`) 配合不同透明度的次级文本。
  - 强调色：暖金色 (`--accent: #D4A574`) 用于按钮、高亮、边框及状态指示，营造专业且温暖的学术氛围。
- **圆角与阴影**：定义了 `8px/12px/16px` 三级圆角 (`--radius-sm/md/lg`) 以及玻璃拟态阴影 (`--glass-shadow`) 和模糊效果 (`--glass-blur: blur(20px)`)。
- **动效**：统一使用 `0.2s cubic-bezier(0.4, 0, 0.2, 1)` 作为过渡曲线。

### 2. 布局架构
采用 **CSS Grid** 实现经典的三栏式桌面布局：
- **左侧边栏 (260px)**：文件树与技能面板，支持 Tab 切换。
- **中间主区 (1fr)**：聊天交互区，包含消息流、欢迎屏及底部输入框。
- **右侧边栏 (280px)**：历史对话列表。
- **响应式策略**：目前主要为固定像素宽度的桌面端适配，通过 `overflow: hidden` 和 `flex` 布局确保内容在视窗内的自适应滚动。

### 3. 组件样式约定
- **消息气泡**：用户消息与 AI 消息通过不同的 Avatar 背景和边框区分，AI 消息支持 Markdown 渲染样式（代码块、表格、引用块等）。
- **玻璃拟态 (Glassmorphism)**：设置页面、预览面板及快速操作按钮广泛使用 `backdrop-filter: blur()` 配合半透明背景，增强层级感。
- **学术可视化组件**：为引用图谱、论文卡片、质量雷达等专业组件定义了专用的类名（如 `.citation-graph-container`, `.quality-radar`），并集成了 Recharts 和 Cytoscape 的默认样式覆盖。

### 4. 开发者规范
- **禁止内联样式**：除动态计算值外，所有样式应通过 CSS 类名调用。
- **变量优先**：修改颜色、间距或字体时，必须优先使用 `var(--token-name)`，严禁硬编码色值。
- **滚动条定制**：全局统一了 `::-webkit-scrollbar` 样式，保持细窄、半透明的滚动条外观。
- **字体栈**：优先使用 `Geist`、`Inter` 及系统默认无衬线字体，代码块强制使用 `JetBrains Mono` 等等宽字体。