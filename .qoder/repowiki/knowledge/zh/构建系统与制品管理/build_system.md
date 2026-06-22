Scholar Studio 采用多语言、多目标的混合构建体系，主要涵盖 Python 核心引擎打包、IDE 插件分发以及 Lean4 形式化验证模块的 CI 集成。

### 1. Python 核心引擎构建
- **包管理**：使用 `pyproject.toml` (Setuptools) 定义项目元数据与依赖，同时保留 `requirements.txt` 用于快速环境初始化。入口点定义为 `scholar.cli:main`。
- **可执行文件打包**：通过 `build_exe.py` 脚本驱动 `PyInstaller` 进行跨平台（主要针对 Windows）打包。支持 `onedir`（推荐，启动快）和 `--onefile`（单文件，体积小但启动慢）两种模式。`scholar.spec` 文件中详细配置了 `hiddenimports` 以解决动态导入问题，并排除了 `torch`, `numpy` 等大型非必要依赖以优化体积。
- **开发模式安装**：提供 `python build_exe.py --install` 选项，通过 `pip install -e .` 将 `scholar` 命令注册到全局环境，便于本地调试。

### 2. IDE 插件分发体系
- **自动化组装**：`build_plugin.py` 负责从 `.qoder/` 目录提取 Skills、Commands、Rules 和 Hooks，并将其复制到 `plugin/` 目录。
- **版本化打包**：脚本读取 `plugin/.qoder-plugin/plugin.json` 中的版本号，自动生成 `scholar-studio-{version}.zip` 分发包，确保插件内容与元数据版本一致。

### 3. Lean4 形式化验证模块
- **构建工具**：位于 `LEAN/` 子目录，使用 Lean 官方构建工具 `Lake` (`lakefile.toml`) 管理 `AiEvolution` 库及 `aievolution` 可执行目标。
- **CI 集成**：通过 `.github/workflows/lean_action_ci.yml` 配置了 GitHub Actions，利用 `leanprover/lean-action@v1` 在每次推送或 PR 时自动执行编译与验证，确保形式化定理的逻辑一致性。

### 4. 基础设施与环境
- **服务编排**：使用 `infra/docker-compose.yml` 统一管理 PostgreSQL (含 pgvector) 和 Neo4j 数据库容器，通过 `init.sql` 自动初始化 Schema，为 RAG 和知识图谱提供底层存储支持。
- **测试规范**：通过 `pytest.ini` 配置测试路径与标记（如 `slow`, `integration`），配合 `test/` 目录下的单元测试与端到端测试保障代码质量。