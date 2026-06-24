## 1. 核心系统与工具
- **技术栈**: React + TypeScript + Vite + Tauri (桌面端)。
- **样式方案**: 纯 CSS (Vanilla CSS)，未使用 Tailwind、Sass 或 CSS-in-JS 库。
- **设计方法论**: 基于 CSS Custom Properties (CSS Variables) 的设计令牌 (Design Tokens) 系统，采用 BEM 风格的类名命名规范。

## 2. 视觉风格：Discourse Dark Theme
UI 采用深色学术风格，强调沉浸感与低对比度背景，辅以暖色调强调色。
- **背景色**: `#3F3D3C` (Base), `#464443` (Elevated)。
- **文本色**: `#FBF7EF` (Primary), 配合不同透明度的次要文本。
- **强调色 (Accent)**: `#D4A574` (暖金色/铜色)，用于按钮、高亮、激活状态及光晕效果。
- **视觉效果**: 广泛使用 `backdrop-filter: blur(20px)` 实现毛玻璃质感，配合柔和的阴影 (`glass-shadow`)。

## 3. 关键文件与架构
- **`desktop/src/App.css`**: 全局样式入口。定义了 `:root` 下的所有设计令牌（颜色、圆角、过渡曲线），以及布局网格、滚动条、Markdown 渲染样式和各类组件的通用类。
- **`desktop/src/components/*.tsx`**: 组件通过导入 `App.css` 中的类名进行样式绑定。主要组件包括 `ChatView`, `SettingsPage`, `FileTree`, `PaperReader` 等。
- **`desktop/vite.config.ts`**: 构建配置，处理 React 插件及 Tauri 开发服务器端口。

## 4. 开发规范与约定
- **设计令牌优先**: 严禁在组件中硬编码颜色值或尺寸。必须使用 `var(--bg-base)`, `var(--accent)`, `var(--radius-md)` 等变量。
- **布局结构**: 采用 CSS Grid 三栏布局 (`260px 1fr 280px`)，分别对应左侧文件树、中间聊天主区、右侧会话历史/工具面板。
- **交互反馈**: 所有可点击元素需遵循 `var(--transition)` (0.2s cubic-bezier) 的过渡动画。悬停状态通常表现为背景色变亮 (`--bg-hover`) 或边框颜色增强。
- **Markdown 渲染**: `.markdown-body` 类定义了 AI 回复内容的排版规范，包括代码块背景、引用块左侧强调色边框、表格样式等。
- **响应式策略**: 目前主要针对桌面端固定视口 (`100vh`) 优化，未观察到复杂的移动端媒体查询断点，符合 Tauri 桌面应用特征。