Scholar Studio 采用多语言混合架构，针对 Python 后端、Lean4 形式化验证模块、Tauri 桌面应用（Rust + TypeScript）分别建立了独立的依赖管理策略。

### 1. Python 后端 (`pyproject.toml` & `requirements.txt`)
- **声明方式**：同时维护 `pyproject.toml`（现代标准）和 `requirements.txt`（传统兼容）。
- **包管理器**：推荐使用支持 `pyproject.toml` 的现代工具（如 `pip` 或 `uv`）。
- **核心依赖**：
  - `typer`, `rich`: CLI 交互与美化。
  - `psycopg2-binary`, `neo4j`: 数据库连接（PostgreSQL, Neo4j）。
  - `PyMuPDF`, `bibtexparser`: 论文解析。
  - `mcp`: Model Context Protocol 支持。
- **版本策略**：使用最小版本约束（如 `>=0.9.0`），未提供全局锁文件（`requirements.lock`），依赖稳定性依赖于开发环境的局部锁定或 CI 缓存。

### 2. Lean4 形式化验证 (`LEAN/lakefile.toml`)
- **构建系统**：使用 Lean4 官方包管理器 **Lake**。
- **依赖锁定**：通过 `lake-manifest.json` 严格锁定所有传递性依赖的 Git Commit Hash，确保形式化证明的可复现性。
- **核心依赖**：
  - `mathlib`: 数学基础库（本地路径引用 `.lake/packages/mathlib`）。
  - `leanprover-community/*`: 包括 `plausible`, `aesop`, `batteries` 等社区标准库。
- **工具链**：通过 `lean-toolchain` 指定 Lean 版本（当前为 `lean4-local`，暗示可能使用本地编译或特定环境版本）。

### 3. 桌面端前端 (`desktop/package.json`)
- **包管理器**：npm (Lockfile v3)。
- **注册源**：配置为国内镜像 `https://registry.npmmirror.com`（见于 `package-lock.json`）。
- **核心依赖**：
  - `@tauri-apps/api`: Tauri 前端桥接。
  - `react`, `cytoscape`, `recharts`: UI 框架与可视化。
  - `katex`, `react-markdown`: 学术公式与文档渲染。
- **版本策略**：使用 Caret 范围（`^`），依赖 `package-lock.json` 进行精确版本锁定。

### 4. 桌面端后端 (`desktop/src-tauri/Cargo.toml`)
- **包管理器**：Cargo (Rust)。
- **核心依赖**：
  - `tauri`: 桌面应用框架。
  - `tauri-plugin-dialog`, `tauri-plugin-log`: 官方插件。
  - `serde`: 序列化支持。
- **版本策略**：遵循 Rust 生态惯例，通过 `Cargo.lock`（未直接读取但隐含存在）锁定版本。

### 开发者规范
1. **Python 依赖更新**：修改 `pyproject.toml` 后需同步更新 `requirements.txt`（若用于部署）。
2. **Lean 依赖同步**：修改 `lakefile.toml` 后必须提交更新后的 `lake-manifest.json` 以锁定新依赖。
3. **前端依赖安装**：由于配置了国内镜像，在国内网络环境下可直接 `npm install`；跨平台协作时需注意 `package-lock.json` 的完整性。
4. **环境隔离**：各子模块（`LEAN`, `desktop`）拥有独立的依赖上下文，严禁在根目录混用不同语言的包管理命令。