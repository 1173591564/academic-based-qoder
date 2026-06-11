# Scholar Studio Plugin

> **本插件是"大脑"，还需要安装"身体"。** Plugin 提供 22 个 Skills + 4 个 Commands + MCP 配置，但实际执行依赖主仓库的 Python 后端和数据库。

## 架构说明

```
┌─────────────────────────────────┐
│  Scholar Studio Plugin（本插件）  │  ← Skills / Commands / Rules / Hooks
│  告诉 AI "做什么、怎么做"         │
└──────────────┬──────────────────┘
               │ 调用
┌──────────────▼──────────────────┐
│  academic-based-qoder（主仓库）   │  ← scholar CLI + MCP Server + Docker
│  真正执行搜索、解析、检索等任务    │
└─────────────────────────────────┘
```

## 安装步骤

### 第一步：安装后端（主仓库）

```bash
# 1. 克隆主仓库
git clone https://gitee.com/gu-yulong1217317/academic-based-qoder.git
cd academic-based-qoder

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 启动 PostgreSQL + Neo4j（需 Docker）
./startup.ps1

# 4. 全量初始化（解析论文、建索引、导入图谱，约 30 分钟）
python -m scholar bootstrap
```

> 以上命令中的 `scholar` 是主仓库里的 Python 包（`scholar/` 目录），不是本插件提供的。

### 第二步：安装本插件

在 QoderWork → 插件市场中搜索 **Scholar Studio** 并安装，或手动导入 `scholar-studio-1.0.0.zip`。

### 第三步：验证

安装完成后，在 QoderWork 对话中输入：
- `调研 Transformer` → 自动触发 `/research-survey`
- `知识库状态` → 自动触发 `/stats` 命令

## 包含能力

| 类型 | 数量 | 说明 |
|------|------|------|
| Skills | 22 | 18 原子 + 4 组合 Workflow |
| Commands | 4 | stats / find / paper / health |
| Rules | 1 | Agent 角色定义 |
| Hooks | 2 | 任务完成通知 + 危险命令拦截 |
| MCP Server | 1 | Scholar MCP（29 工具） |

## Skills 列表

### 原子 Skills
- `/research-survey` — 全面文献调研
- `/deep-read` — 单篇深度阅读
- `/paper-compare` — 多篇对比
- `/paper-recommendation` — 论文推荐
- `/cold-start` — 陌生领域入门
- `/related-work` — 写 Related Work
- `/citation-network` — 引用网络分析
- `/research-gap` — 研究空白发现
- `/concept-evolution` — 概念演化追踪
- `/formula-derivation` — 公式推导
- `/math-verification` — Lean4 验证
- `/experiment-code` — 实验代码生成
- `/quality-check` — 质量评分
- `/review-report` — 审稿报告
- `/paper-ingestion` — 论文导入
- `/bibtex-management` — BibTeX 管理
- `/kb-maintenance` — 知识库维护
- `/reading-progress` — 阅读进度

### 组合 Workflow
- `/full-research` — 调研 → 精读 → 对比 → Related Work
- `/gap-analysis-flow` — 引用网络 → 概念演化 → 研究缺口 → 推荐
- `/paper-analysis-flow` — 精读 → 评分 → 推导 → 代码
- `/writing-flow` — 调研 → 对比 → 写作 → BibTeX → 审稿
