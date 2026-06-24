该项目采用多语言混合架构，针对不同技术栈使用了独立的依赖管理系统：

### 1. Python 后端 (Scholar Studio)
- **管理工具**：同时维护 `pyproject.toml` (现代标准) 和 `requirements.txt` (传统兼容)。
- **依赖声明**：在 `pyproject.toml` 中定义了核心依赖（如 `typer`, `rich`, `psycopg2-binary`, `neo4j`, `PyMuPDF` 等）。
- **版本策略**：采用最小版本约束（例如 `>=0.9.0`），未提供锁文件（如 `poetry.lock` 或 `Pipfile.lock`），依赖解析具有不确定性。
- **构建系统**：使用 `setuptools` 作为构建后端。

### 2. 前端桌面应用 (Desktop - Tauri/React)
- **管理工具**：使用 `npm` (Node.js)。
- **锁文件**：存在 `package-lock.json` (lockfileVersion 3)，确保了依赖树的确定性安装。
- **依赖范围**：包括 React 生态、Tauri API、Cytoscape (图谱可视化) 以及 Markdown/LaTeX 渲染库。
- **私有源**：从锁文件可见，部分包从 `npmmirror.com` 拉取，表明配置了国内镜像源以加速下载。

### 3. Lean 形式化验证模块 (LEAN)
- **管理工具**：使用 Lake (Lean 4 的官方构建与包管理器)。
- **配置文件**：`lakefile.toml` 定义项目名称与目标，`lake-manifest.json` 记录精确的依赖快照。
- **依赖来源**：主要依赖 `mathlib` (本地路径引用) 以及多个来自 `leanprover-community` 的 Git 仓库（如 `plausible`, `aesop`, `batteries`）。
- **版本锁定**：通过 `lake-manifest.json` 中的 Git Commit Hash (`rev`) 严格锁定第三方库版本，确保形式化证明的可复现性。
- **工具链**：通过 `lean-toolchain` 指定使用的 Lean 版本（当前为 `lean4-local`）。

### 开发约定与建议
- **Python 环境**：建议优先使用 `pip install -e .` 基于 `pyproject.toml` 进行开发安装，以保持与构建系统的一致性。
- **前端开发**：严禁手动修改 `package-lock.json`，应通过 `npm install` 或 `npm update` 管理依赖变更。
- **Lean 同步**：在更新 Lean 依赖后，需提交更新后的 `lake-manifest.json` 以同步团队间的依赖版本。