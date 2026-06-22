该仓库采用双语言混合的依赖管理策略，分别针对 Python 后端引擎和 Lean4 形式化验证模块使用不同的包管理工具。

### 1. Python 依赖管理 (Scholar Studio)
- **核心工具**：使用 `setuptools` 作为构建后端，通过 `pyproject.toml` 定义项目元数据和核心依赖。同时保留 `requirements.txt` 用于快速环境部署或 CI/CD 流程。
- **依赖声明**：
  - 在 `pyproject.toml` 中声明了核心依赖（如 `typer`, `rich`, `psycopg2-binary`, `neo4j`, `PyMuPDF`）以及可选依赖组（`mcp`）。
  - `requirements.txt` 内容与 `pyproject.toml` 保持同步，并包含了一些注释掉的可选依赖（如 `ulid`, `datasets`），表明项目支持渐进式功能增强。
- **版本控制**：采用语义化版本约束（如 `>=0.9.0`），未使用严格的锁定文件（如 `poetry.lock` 或 `Pipfile.lock`），依赖解析依赖于安装时的 PyPI 最新兼容版本。
- **私有源/镜像**：未发现显式的 `pip.conf` 或私有注册表配置，默认使用公共 PyPI。

### 2. Lean4 依赖管理 (LEAN 模块)
- **核心工具**：使用 Lean4 官方包管理器 **Lake**。
- **配置文件**：
  - `lakefile.toml`：定义项目名称 `AiEvolution`、版本及构建目标。
  - `lake-manifest.json`：锁定所有传递性依赖的具体 Git 提交哈希（rev），确保构建的可复现性。例如，`mathlib` 被声明为本地路径依赖（`type: path`），而 `plausible`, `aesop`, `batteries` 等社区库则通过 Git URL 锁定特定版本。
  - `lean-toolchain`：指定使用的 Lean 工具链版本为 `lean4-local`，暗示开发环境可能使用本地编译或特定配置的 Lean 发行版。
- **依赖来源**：主要依赖来自 `leanprover-community` 组织的官方生态库，通过 Git 进行版本追踪。

### 3. 开发者规范
- **Python 环境**：建议通过 `pip install -e .` 安装开发模式，或使用 `pip install -r requirements.txt` 快速同步依赖。若需 MCP 功能，需安装 `[mcp]` 可选组。
- **Lean 环境**：进入 `LEAN/` 目录后，应使用 `lake update` 更新依赖锁文件，并使用 `lake build` 进行构建。注意 `mathlib` 目前配置为本地路径依赖，需确保 `.lake/packages/mathlib` 存在或修改为远程 Git 依赖。