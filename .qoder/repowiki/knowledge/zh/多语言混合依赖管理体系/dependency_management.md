Scholar Studio 采用多语言混合架构，针对 Python 后端、Tauri 桌面前端（React + Rust）以及 Lean 形式化验证模块分别建立了独立的依赖管理体系。

### 1. Python 后端 (Scholar CLI & MCP)
- **管理工具**：同时维护 `pyproject.toml` (PEP 621 标准) 和 `requirements.txt`。
- **核心依赖**：
  - `typer`, `rich`: 构建 CLI 交互界面。
  - `psycopg2-binary`, `neo4j`: 关系型数据库与图数据库驱动。
  - `PyMuPDF`, `bibtexparser`: 论文解析与文献处理。
  - `mcp`: Model Context Protocol 支持。
- **版本策略**：在 `pyproject.toml` 中使用宽松的版本约束（如 `>=0.9.0`），便于获取最新功能；`requirements.txt` 作为备选安装入口，保持同步。
- **构建系统**：使用 `setuptools` 作为构建后端，定义了 `scholar` 命令行入口点。

### 2. 桌面应用前端 (Tauri + React)
- **Node.js 依赖**：通过 `desktop/package.json` 管理。
  - **UI 框架**：React 19, Vite 8。
  - **可视化**：`cytoscape` (图谱), `recharts` (图表), `katex` (公式渲染)。
  - **Tauri 集成**：`@tauri-apps/api` 及插件 (`dialog`)。
- **Rust 后端依赖**：通过 `desktop/src-tauri/Cargo.toml` 管理。
  - **核心库**：`tauri` (v2.11.3), `serde` (序列化), `tauri-plugin-log/dialog`。
  - **版本锁定**：依赖 Cargo 的 `Cargo.lock` 机制确保 Rust 依赖的确定性构建。

### 3. Lean 形式化验证模块
- **管理工具**：使用 Lean 4 的官方包管理器 **Lake**。
- **配置文件**：`LEAN/lakefile.toml` 定义项目元数据，`LEAN/lake-manifest.json` 锁定依赖版本。
- **核心依赖**：
  - `mathlib`: 数学标准库（通过 path 类型本地引用或远程同步）。
  - `leanprover-community` 生态：`plausible`, `aesop`, `proofwidgets`, `batteries` 等。
- **版本控制**：`lake-manifest.json` 记录了每个 Git 依赖的具体 commit hash (`rev`) 和输入修订版 (`inputRev`)，确保了形式化证明环境的严格一致性。

### 开发规范
- **隔离性**：各语言栈依赖互不干扰，通过目录结构 (`desktop/`, `LEAN/`, 根目录) 物理隔离。
- **锁定机制**：前端和 Lean 模块使用了严格的锁定文件 (`package-lock.json`, `lake-manifest.json`)，Python 模块建议在生产环境通过 `pip freeze` 生成锁定文件以确保复现性。