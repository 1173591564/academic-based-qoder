# Scholar Studio — AI 学术研究助手

基于 Qoder IDE 的学术研究引擎，管理 **440 篇 AI 演化方向论文**，提供 RAG 语义检索、Neo4j 引用图谱、14 个学术 skills（8 原子 + 6 工作流）和 Lean4 形式化验证。

> **核心理念**：把 440 篇论文的 TeX 源码变成可查询、可推理、可组合的学术数据层，然后通过 Qoder Agent + Skills 自动化完成调研→精读→对比→写作的全流程。

---

## 从零开始：5 分钟搭建

### 系统要求

| 组件 | 最低版本 | 用途 | 安装 |
|------|---------|------|------|
| Docker Desktop | 4.x+ | PostgreSQL + Neo4j 容器 | [下载](https://www.docker.com/products/docker-desktop/) |
| Python | 3.10+ | CLI 工具集 + MCP Server | [下载](https://www.python.org/downloads/) |
| Qoder IDE | 最新版 | Agent + Skills + MCP 集成 | [下载](https://qoder.com/) |
| Git | 任意版本 | 代码版本管理 | [下载](https://git-scm.com/) |

> **Windows 用户注意**：如果同时使用 VMware，Docker Desktop 的 WSL2 后端可能冲突。启动 Docker 前确保 WSL2 已启用：`wsl --set-default-version 2`

### Step 1: 克隆仓库

```bash
git clone https://gitee.com/gu-yulong1217317/academic-based-qoder.git
cd academic-based-qoder
```

### Step 2: 安装 Python 依赖

```bash
# 推荐先创建虚拟环境
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt
```

依赖清单（`requirements.txt`）：

| 包 | 用途 |
|---|------|
| `typer` + `rich` | CLI 框架 + 终端美化输出 |
| `psycopg2-binary` | PostgreSQL 连接 |
| `neo4j` | Neo4j 图数据库驱动 |
| `python-dotenv` | 环境变量加载 |
| `PyMuPDF` | PDF 论文处理 |
| `mcp` | MCP Server 协议（Qoder 集成） |

### Step 3: 配置环境变量

在项目根目录创建 `.env` 文件：

```env
# 智谱 embedding API（RAG 语义搜索必需）
# 获取方式：https://open.bigmodel.cn/ → 注册 → API Keys
SCHOLAR_EMBEDDING_API_KEY=your_api_key_here
```

> **没有 API Key 也能用**：只是 RAG 语义搜索不可用，全文搜索、图谱分析、Skills 执行都正常。
>
> 数据库密码**不需要**放在 `.env` 中，由 Docker 容器内部管理（见 `infra/docker-compose.yml`）。

### Step 4: 启动数据库

```powershell
.\startup.ps1
```

脚本自动完成：
1. 启动 Docker 容器（`infra/docker-compose.yml`）
2. 等待 PostgreSQL（端口 **5433**）和 Neo4j（端口 **7474/7687**）健康检查通过
3. 显示当前知识库统计

容器信息：

| 容器 | 镜像 | 端口 | 凭证 |
|------|------|------|------|
| `scholar-pg` | `pgvector/pgvector:pg16` | 5433 | scholar / scholar2024 |
| `scholar-neo4j` | `neo4j:5-community` | 7474, 7687 | neo4j / scholar2024 |

> 端口 5433 而非常规 5432，避免与本地已安装的 PostgreSQL 冲突。

### Step 5: 全量初始化（Bootstrap）

```bash
python -m scholar bootstrap
```

Bootstrap 按顺序执行 **9 步**，全程约 **40 分钟**：

| # | 命令 | 产出 | 耗时 |
|---|------|------|------|
| 1 | `parse-all` | 440 篇论文的 TeX → JSON | ~5 min |
| 2 | `year-fix` | 补全缺失年份（交叉引用 Lean4） | ~1 min |
| 3 | `author-fix` | 补全缺失作者 | ~1 min |
| 4 | `graph-build` | Neo4j 图谱（25K 节点 + 38K 边） | ~3 min |
| 5 | PG sync | PostgreSQL 写入 sections/formulas/citations | ~2 min |
| 6 | `rag-index` | 向量索引 45K chunks（需 API Key） | ~30 min |
| 7 | `auto-notes` | 自动生成 439 份阅读笔记 | ~3 min |
| 8 | `quality-score` | 423 篇论文 7 维度评分 | ~2 min |
| 9 | `classify` | 417 篇论文领域分类 | ~1 min |

> **断点续传**：如果中途中断，重新运行 `bootstrap` 会自动跳过已完成的步骤。

### Step 6: 在 Qoder 中打开

1. 用 Qoder 打开项目目录
2. Qoder 自动读取 `.qoder/mcp.json`，后台启动 **Scholar MCP Server**（29 个工具）
3. 在对话框中直接开始使用

### Step 7: 验证一切正常

在 Qoder 对话框中输入：

```
你：查看知识库状态
```

或直接在终端运行：

```bash
python -m scholar stats
```

期望输出：

```
📊 Scholar Studio Knowledge Base
  Papers:        440 (parsed)
  Sections:      13,719
  Formulas:      5,064
  Citations:     36,477
  RAG Chunks:    45,405
  Notes:         439
  Quality:       423 (A:93 B:262 C:59 D:9)
  Classified:    417
```

---

## 快速开始（已部署用户）

### 启动数据库

```powershell
.\startup.ps1
```

### 对话即可使用

```
你：调研 Transformer 的注意力机制演进
你：精读 01KT6MTBBH03MN0Z6PK902XKC2
你：写 Attention 方向的 Related Work
```

### 一键开始（Deeplinks）

点击链接直接唤起 Qoder 并开始任务：

| 任务 | 说明 |
|------|------|
| [调研 Transformer](qoder://aicoding.aicoding-deeplink/chat?text=%E8%B0%83%E7%A0%94+Transformer+%E6%B3%A8%E6%84%8F%E5%8A%9B%E6%9C%BA%E5%88%B6%E7%9A%84%E5%8F%91%E5%B1%95%E5%8E%86%E7%A8%8B%EF%BC%8C%E6%8C%89%E6%97%B6%E9%97%B4%E7%BA%BF%E6%95%B4%E7%90%86%E5%85%B3%E9%94%AE%E8%AE%BA%E6%96%87&mode=agent) | 按时间线整理注意力机制关键论文 |
| [精读 Attention Is All You Need](qoder://aicoding.aicoding-deeplink/chat?text=%E7%B2%BE%E8%AF%BB%E8%AE%BA%E6%96%87+01KT6MTBBH03MN0Z6PK902XKC2+%28Attention+Is+All+You+Need%29%EF%BC%8C%E8%BE%93%E5%87%BA%E7%BB%93%E6%9E%84%E5%8C%96%E5%88%86%E6%9E%90&mode=agent) | 结构化分析经典论文 |
| [RLHF 研究空白](qoder://aicoding.aicoding-deeplink/chat?text=%E5%88%86%E6%9E%90+RLHF+%E5%92%8C+DPO+%E6%96%B9%E5%90%91%E7%9A%84%E7%A0%94%E7%A9%B6%E7%A9%BA%E7%99%BD%E5%92%8C%E6%9C%AA%E6%9D%A5%E6%96%B9%E5%90%91&mode=agent) | 分析 RLHF/DPO 的研究缺口 |
| [入门 State Space Model](qoder://aicoding.aicoding-deeplink/chat?text=%E5%85%A5%E9%97%A8+State+Space+Model%EF%BC%8C%E5%BB%BA%E7%AB%8B%E7%9F%A5%E8%AF%86%E5%9B%BE%E8%B0%B1%E5%92%8C%E5%AD%A6%E4%B9%A0%E8%B7%AF%E5%BE%84&mode=agent) | 建立知识图谱和学习路径 |

---

## 14 个学术 Skills

在 Qoder 对话中直接使用，或输入 `/skill-name` 触发：

### 原子 Skills（8 个）

| 类别 | Skill | 用法示例 |
|------|-------|--------|
| **论文管理** | `paper-ingestion` | "导入新论文" |
| **数学验证** | `math-verification` | "用 Lean4 验证这个定理" |
| **论文推荐** | `paper-recommendation` | "推荐接下来该读什么" |
| **引用分析** | `citation-network` | "分析 NLP 领域的引用网络" |
| **研究缺口** | `research-gap` | "找 RLHF 方向的研究空白" |
| **审稿报告** | `review-report` | "写一篇审稿报告" |
| **入门引导** | `cold-start` | "入门 State Space Model" |
| **实验代码** | `experiment-code` | "复现 LoRA 的实验代码" |

每个 skill 末尾都有 **Next Steps** 引导，执行完后自动建议下一步操作。

### 工作流（6 个）

串联多个原子 skill，自动传递数据，一键完成完整研究流程：

| Workflow | 链路 | 用法示例 |
|----------|------|--------|
| `research-survey` | RAG + 图谱 + 分类 + 时间线 | "调研 Diffusion Model 的发展历程" |
| `paper-deep-dive` | 精读 + 质量 + 推导 + 代码 | "深度分析 Attention Is All You Need" |
| `writing-pipeline` | 调研 → 撰写 → 编译 → 审稿 | "帮我写一篇论文" |
| `reproduce-paper` | 环境 → 代码 → 运行 → 对比 | "复现这篇论文的实验" |
| `idea-to-paper` | 调研 → 写作 → 复现 → 成文 | "我有一个想法" |
| `kb-management` | 健康检查 + 自动更新 + 入库 | "维护知识库" |

---

## 架构概览

```
┌─────────────────────────────────────────────────────┐
│                    Qoder IDE                         │
│                                                     │
│  ┌─────────┐   ┌──────────┐   ┌─────────────────┐ │
│  │  Rules   │   │ 22 Skills│   │  Hooks/Commands  │ │
│  │ (always) │   │ (SKILL.md│   │  (自动化/快捷)   │ │
│  └────┬─────┘   └────┬─────┘   └─────────────────┘ │
│       │              │                               │
│       ▼              ▼                               │
│  ┌────────────────────────────────┐                 │
│  │   Scholar MCP Server (41 工具)  │                 │
│  │   (Qoder ↔ CLI 桥接层)          │                 │
│  └────────────┬───────────────────┘                 │
└───────────────│─────────────────────────────────────┘
                │  CLI 命令
                ▼
┌───────────────────────────────────────────────────────┐
│              scholar/ Python CLI                       │
│                                                       │
│   ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│   │ 论文解析  │  │ 图谱构建  │  │ RAG 向量索引      │  │
│   │ TeX→JSON │  │ Neo4j    │  │ embedding + search│  │
│   └────┬─────┘  └────┬─────┘  └────────┬─────────┘  │
└────────│─────────────│─────────────────│─────────────┘
         │             │                 │
         ▼             ▼                 ▼
┌──────────────┐ ┌───────────┐  ┌─────────────────┐
│ PostgreSQL   │ │  Neo4j    │  │ data/papers/    │
│ + pgvector   │ │  概念图谱  │  │ 445 篇论文源文件 │
│ 端口 5433    │ │  端口 7474 │  │ (PDF + TeX)     │
└──────────────┘ └───────────┘  └─────────────────┘
```

### 数据流

```
论文 TeX 源码 → parse → JSON (parsed/<ULID>.json)
    ↓                        ↓
PostgreSQL (sections,     Neo4j (papers, concepts,
 formulas, citations)      REPLACES 关系)
    ↓
RAG 向量索引 (45K chunks, 智谱 embedding-2)
```

---

## CLI 命令参考

```bash
# 论文库
python -m scholar stats                     # 知识库统计
python -m scholar search "attention"        # 全文搜索
python -m scholar list-papers --year 2024   # 按年份列出
python -m scholar info <ULID>               # 论文详情
python -m scholar export-bib                # 导出 BibTeX

# 图谱查询（需 Neo4j 运行）
python -m scholar graph-stats               # 图谱统计
python -m scholar graph-query "attention"   # 概念查询
python -m scholar cite-network              # 全局引用网络
python -m scholar cite-network <ULID>       # 单篇前后向引用

# 语义搜索（需 RAG 索引 + API Key）
python -m scholar rag-search "query"        # 向量搜索
python -m scholar rag-search "q" --hybrid   # 混合搜索（向量+BM25+RRF）

# 批处理
python -m scholar auto-notes                # 生成全部阅读笔记
python -m scholar quality-score --all       # 7 维度评分（A-F）
python -m scholar classify --all            # 领域/子领域/方法分类

# 编排
python -m scholar bootstrap                 # 全量初始化（首次部署）
python -m scholar ingest <ULID>             # 增量导入单篇

# 外部
python -m scholar arxiv-search "query"      # 搜索 arXiv
```

---

## 项目结构

```
.qoder/
  rules/           Agent 规则（identity, pipelines, tools, academic）
  skills/          14 个学术 skills（8 原子 + 6 工作流）
  commands/        4 个快捷指令（stats, find, paper, health）
  hooks/           2 个自动化钩子（任务通知 + 危险拦截）
  settings.json    Hooks 配置
  mcp.json         MCP Server 配置

data/papers/       445 篇论文（每篇：paper.pdf + source.tar.gz）
output/
  parsed/          440 篇结构化 JSON（核心数据源）
  notes/           阅读笔记 + 质量评分 JSON
  drafts/          综述、Related Work、报告
  bib/             BibTeX 文件
  experiments/     实验代码复现

LEAN/              Lean4 形式化验证（125 创新节点 + 7 定理）
scholar/           Python CLI 工具集（35 命令）
scholar_mcp/       MCP Server（41 工具，Qoder 桥接层）
infra/             Docker 编排（PostgreSQL + Neo4j）
  docker-compose.yml
  init.sql         PostgreSQL 建表脚本（papers, sections, formulas, citations, chunks）
```

---

## 数据规模

| 数据层 | 数量 |
|--------|------|
| 论文 | 440 篇（TeX 源文件解析） |
| Sections | 13,719 |
| Formulas | 5,064 |
| Citations | 36,477 |
| RAG Chunks | 45,405 |
| Neo4j Nodes | 25,131 |
| Neo4j Edges | 38,485 |
| 阅读笔记 | 439 |
| 质量评分 | 423（A:93 B:262 C:59 D:9） |
| 领域分类 | 417 |

---

## 自定义改造：换成你自己的论文库

Scholar Studio 可以管理**任意领域**的 TeX 论文。以下步骤把它改造成你自己的学术研究助手：

### 1. 准备论文

将你的论文放入 `data/papers/<ULID>/` 目录，每篇论文一个文件夹：

```
data/papers/
  01KT6MTBBH03MN0Z6PK902XKC2/
    paper.pdf           # PDF 原文（可选，用于展示）
    source.tar.gz       # TeX 源文件压缩包（必须，用于解析）
```

> **ULID 命名**：每个文件夹名用 ULID 格式（26 位字母数字），可用在线工具生成：https://ulidgenerator.com/
>
> **TeX 源文件**：压缩包内包含 `.tex`、`.bib` 等文件。Scholar 解析 TeX 提取标题、摘要、章节、公式、引用。

### 2. 批量导入

```bash
# 扫描所有论文
python -m scholar scan

# 批量解析
python -m scholar parse-all

# 补全缺失年份和作者
python -m scholar year-fix
```

### 3. 重建数据层

```bash
# 重建图谱（Neo4j）
python -m scholar graph-build

# 重建 RAG 索引（需 API Key）
python -m scholar rag-index

# 生成阅读笔记 + 质量评分 + 分类
python -m scholar auto-notes
python -m scholar quality-score --all
python -m scholar classify --all
```

### 4. 更新 Lean4 形式化层（可选）

编辑 `LEAN/AiEvolution/Database.lean`，添加你的领域的创新节点和定理。然后重新编译：

```bash
cd LEAN && lake build
```

### 5. 修改 Agent 规则

编辑 `.qoder/rules/identity.md`，更新项目描述和心智模型，让 Agent 适配你的研究方向。

---

## 自动化 Hooks

配置在 `.qoder/settings.json`，Qoder 重启后生效：

| Hook | 事件 | 作用 |
|------|------|------|
| `task-done.ps1` | Stop | Agent 完成任务后弹出 Windows 桌面通知 |
| `block-dangerous.ps1` | PreToolUse | 拦截 `DROP TABLE`、`docker rm` 等危险操作 |

## 快捷指令

放在 `.qoder/commands/`，在对话中输入 `/` 即可调用：

| 指令 | 用法 |
|------|------|
| `/stats` | 查看知识库状态（论文数、图谱、RAG 覆盖） |
| `/find` | 全文 + 语义混合搜索论文 |
| `/paper` | 查看单篇论文详情 + 引用关系 |
| `/health` | 知识库健康检查 + 修复建议 |

---

## Qoder Plugin

本项目可封装为 **Qoder Plugin**，在 Quest 模式下安装使用。Plugin 包含全部 14 个 Skills + 4 个 Commands + MCP Server。

### 构建 Plugin

```bash
python build_plugin.py
```

产出在 `plugin/` 目录：

```
plugin/
  .qoder-plugin/plugin.json   ← 插件元数据
  skills/                     ← 14 个 Skills
  commands/                   ← 4 个快捷指令
  .mcp.json                   ← MCP Server 配置
```

### 安装使用

1. 在 Qoder Quest 中安装此 Plugin
2. 克隆主仓库并执行 `pip install -r requirements.txt` + `python -m scholar bootstrap`
3. 启动数据库后，所有 14 个 Skills 即可使用

> **本地 IDE 用户**：不需要 Plugin，直接 clone 本仓库即可，`.qoder/skills/` 会自动加载。

---

## 常见问题

### Docker 容器启动失败

```bash
# 检查 Docker 是否在运行
docker info

# 检查端口是否被占用
netstat -ano | findstr "5433"
netstat -ano | findstr "7474"

# 如果端口被占用，修改 infra/docker-compose.yml 中的端口映射
```

### PostgreSQL 连接超时

端口 5433 而非常规 5432，是刻意设计避免冲突。所有连接字符串硬编码了 5433：

```
postgresql://scholar:scholar2024@localhost:5433/scholar
```

### RAG 搜索无结果

1. 确认 `.env` 中有有效的 `SCHOLAR_EMBEDDING_API_KEY`
2. 确认 `python -m scholar rag-index` 已成功执行（45K chunks）
3. 没有 API Key 时，`rag-search` 会自动 fallback 到全文搜索

### Bootstrap 中断恢复

直接重新运行 `python -m scholar bootstrap`，已完成的步骤会自动跳过。如果需要强制重跑某一步：

```bash
python -m scholar parse-all          # 重新解析所有论文
python -m scholar graph-build        # 重建图谱
python -m scholar rag-index          # 重建 RAG 索引（先 TRUNCATE chunks 表）
```

### Windows + VMware 冲突

如果 VMware 使用了 WSL2 后端，Docker Desktop 可能无法启动。解决：

```powershell
# 检查 WSL 状态
wsl --list --verbose

# 如果 Docker Desktop 的 distro 未运行
wsl --shutdown
# 然后重新启动 Docker Desktop
```
