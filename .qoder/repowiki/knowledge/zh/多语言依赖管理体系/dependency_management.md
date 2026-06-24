Scholar Studio 采用多语言混合架构，针对不同技术栈实施了标准化的依赖管理策略：

### 1. Python 后端 (Scholar Core & MCP)
- **包管理器**: 使用 `pyproject.toml` (PEP 621 标准) 作为主要的项目元数据和依赖声明文件，同时保留 `requirements.txt` 用于兼容传统的 pip 安装流程。
- **核心依赖**: 
  - 交互与 CLI: `typer`, `rich`
  - 数据库驱动: `psycopg2-binary` (PostgreSQL), `neo4j` (图数据库)
  - 学术处理: `PyMuPDF` (PDF 解析), `bibtexparser`, `rapidfuzz`
  - 协议支持: `mcp` (Model Context Protocol)
- **版本控制**: 采用最小版本约束（如 `>=0.9.0`），未提供严格的锁文件（如 `poetry.lock` 或 `uv.lock`），在开发环境中依赖 pip 的默认解析机制。

### 2. 桌面客户端 (Tauri + React)
- **前端依赖 (Node.js)**:
  - **管理工具**: `npm` (通过 `package.json` 和 `package-lock.json` 锁定版本)。
  - **核心库**: `react` (UI), `cytoscape` (图谱可视化), `katex` (公式渲染), `@tauri-apps/api` (桥接层)。
- **后端依赖 (Rust)**:
  - **管理工具**: `Cargo` (通过 `Cargo.toml` 声明，`Cargo.lock` 严格锁定版本)。
  - **核心库**: `tauri` (v2 框架), `serde` (序列化), `tauri-plugin-dialog` (系统对话框)。
  - **版本策略**: Rust 侧使用了精确的版本锁定（如 `tauri = "2.11.3"`），确保桌面壳层的稳定性。

### 3. 形式化验证模块 (Lean 4)
- **包管理器**: 使用 Lean 4 原生的 `Lake` 构建系统。
- **配置文件**: `lakefile.toml` 定义项目结构，`lake-manifest.json` 记录依赖树的精确快照。
- **依赖源**: 主要依赖 `mathlib`（数学库）及 `leanprover-community` 下的多个工具库（如 `aesop`, `proofwidgets`）。
- **版本同步**: 通过 `lean-toolchain` 文件指定 Lean 编译器版本（当前指向 `lean4-local`），确保形式化证明环境的一致性。

### 开发者规范
- **Python 环境**: 建议通过 `pip install -r requirements.txt` 或 `pip install .` 初始化环境。
- **桌面开发**: 需同时维护 Node.js 环境（前端资源打包）和 Rust 工具链（原生层编译）。
- **版本更新**: 修改 `pyproject.toml` 或 `package.json` 后，应确保对应的锁文件（`package-lock.json`, `Cargo.lock`, `lake-manifest.json`）同步更新并提交至版本控制系统。