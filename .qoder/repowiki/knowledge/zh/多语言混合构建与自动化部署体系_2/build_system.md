Scholar Studio 采用多语言混合架构（Python, Rust/Tauri, Lean4），其构建系统由多个独立的工具链和自动化脚本协同组成，覆盖了从后端服务、桌面应用到形式化验证模块的全生命周期管理。

### 1. Python 后端构建与分发
- **包管理**：使用 `pyproject.toml` 定义项目元数据与依赖，基于 `setuptools` 进行标准构建。支持通过 `pip install -e ".[dev]"` 进行开发环境安装。
- **可执行文件打包**：提供 `scripts/build_exe.py` 脚本，利用 `PyInstaller` 将 CLI 引擎打包为独立的可执行文件（`.exe`）。支持 `onedir`（默认，启动快）和 `--onefile`（单文件，便于分发）两种模式，并自动处理复杂的 hidden imports 以排除不必要的重型依赖（如 torch, tensorflow）。
- **插件系统构建**：通过 `scripts/build_plugin.py` 自动化生成 AI IDE（Qoder/Claude Code）插件。该脚本从 `.qoder/` 目录同步 Skills、Commands、Rules 和 Hooks 到 `plugin/` 目录，并根据 `plugin.json` 中的版本号自动打包为 `.zip` 分发文件。

### 2. 桌面应用构建 (Tauri + React)
- **前端构建**：位于 `desktop/` 目录，基于 Vite + React + TypeScript。通过 `npm run build` 编译静态资源至 `dist/`。
- **原生壳层打包**：使用 Tauri v2 框架。`tauri.conf.json` 配置了构建钩子，在执行 `cargo tauri build` 时会自动触发前端构建。支持跨平台打包（Windows, macOS, Linux）。

### 3. 形式化验证模块 (Lean4)
- **构建工具**：位于 `LEAN/` 目录，使用 Lean4 的原生构建工具 `lake`。
- **配置**：`lakefile.toml` 定义了 `AiEvolution` 库和 `aievolution` 可执行目标。CI 流程中会尝试运行 `lake build` 以验证定理证明的正确性。

### 4. 基础设施与 CI/CD
- **本地基础设施**：通过 `infra/docker-compose.yml` 一键拉起 PostgreSQL (含 pgvector) 和 Neo4j 数据库，为本地开发和测试提供标准化的数据存储环境。
- **持续集成**：`.github/workflows/test.yml` 配置了自动化测试流水线。在 Ubuntu 环境下安装 Python 依赖，运行 `pytest` 套件，并尝试验证 Lean4 模块的构建状态。

### 5. 开发者约定
- **版本一致性**：各子模块（Python, Desktop, Plugin, Lean）均在各自的配置文件中维护 `0.1.0` 版本号，发布时需同步更新。
- **构建入口**：所有构建操作均封装在 `scripts/` 下的 Python 脚本或标准的 npm/cargo/lake 命令中，避免直接使用复杂的底层工具链参数。