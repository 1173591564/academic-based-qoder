## 1. 核心样式体系
Scholar Studio 的前端采用 **原生 CSS + CSS Variables (Design Tokens)** 的方案，未引入 Tailwind、Bootstrap 或 Styled-components 等第三方 UI 框架。整体视觉风格定义为 **“Discourse Dark Theme”**（类 Discourse 论坛的深色极简风），强调高对比度、玻璃拟态（Glassmorphism）与暖色调点缀。

## 2. 关键文件与架构
- **`desktop/src/App.css`**：全局样式入口，定义了所有 Design Tokens、布局网格、组件类名及 Markdown 渲染样式。
- **`desktop/src/App.tsx`**：应用根组件，负责视图切换（聊天/设置）与错误边界。
- **`desktop/src/components/*.tsx`**：功能组件（如 `ChatView`, `FileTree`, `CitationGraph`），通过 `className` 映射到 `App.css` 中的预定义样式。

## 3. 设计规范与约定
### 3.1 Design Tokens (`:root`)
- **色彩系统**：
  - 背景色：`--bg-base` (#3F3D3C) 与 `--bg-elevated` (#464443) 构成深色基底。
  - 文本色：`--text-primary` (#FBF7EF) 确保在深色背景下的高可读性。
  - 强调色：`--accent` (#D4A574, 暖金色) 用于按钮、选中状态及光晕效果。
- **视觉效果**：
  - 玻璃拟态：通过 `--glass-blur: blur(20px)` 和半透明背景实现侧边栏与弹窗的通透感。
  - 圆角规范：统一使用 `--radius-sm` (8px), `--radius-md` (12px), `--radius-lg` (16px)。

### 3.2 布局策略
- **三栏网格布局**：`.app-layout` 采用 `grid-template-columns: 260px 1fr 280px`，分别对应左侧文件/技能树、中间聊天主区、右侧对话历史。
- **响应式处理**：目前主要针对桌面端（Tauri 环境）固定视口（`100vh`），未涉及复杂的移动端媒体查询。

### 3.3 组件样式约定
- **语义化类名**：采用 BEM 风格的命名（如 `.sidebar-left`, `.chat-header`, `.message-bubble`）。
- **Markdown 渲染**：`.markdown-body` 专门针对 AI 返回的富文本进行了样式重置，包括代码块高亮背景、表格边框及引用块样式。
- **滚动条美化**：全局自定义了 `::-webkit-scrollbar`，使其与深色主题融合，宽度统一为 6px。

## 4. 开发者指南
- **新增组件**：请在 `App.css` 中定义对应的类名，并复用现有的 CSS 变量（如 `var(--bg-surface)`），避免硬编码颜色值。
- **主题扩展**：若需调整配色，仅需修改 `:root` 下的变量定义即可全局生效。
- **图标与字体**：项目依赖系统字体栈（Geist, Inter, PingFang SC），图标目前主要使用 Unicode 字符或 Emoji，未引入大型图标库。