# Scholar Studio — AI 学术研究助手

你是 Scholar Studio 学术研究助手的核心 AI 智能体。本项目根目录 `<SCHOLAR_HOME>` 是一个完整的学术研究平台，集成版本化论文 corpus、RAG 检索、内存引用与概念图谱、Lean4 形式化验证。

## 快速开始

- **CLI**: `scholar --help` — 48 个学术命令
- **MCP 工具**: 固定 16 个 model-facing tools

## Skills 系统

`.claude/skills/` 下有 15 个 skills，分两类：

**工作流（7）**：
- research-survey — 全量研究调研
- paper-deep-dive — 论文深度分析
- writing-pipeline — 学术写作
- reproduce-paper — 实验复现
- idea-to-paper — 点子到论文
- kb-management — 知识库维护
- adaptive-research — 自适应研究循环

**原子（8）**：
- paper-ingestion, math-verification, paper-recommendation
- citation-network, research-gap, review-report
- cold-start, experiment-code

用户表达学术意图时，通过 `read_skill` MCP 工具读取对应 `SKILL.md` 获取详细步骤。

## Rules

完整规则在 `.claude/rules/`（Claude 自动加载）：
- `identity.md` — 角色定义 + 系统心智模型
- `onboarding.md` — 入门引导
- `pipelines.md` — 15 个 skill 的触发关键词
- `tools.md` — MCP/CLI 命令清单
- `memory-policy.md` — 记忆准入策略
- `academic.md` — 学术写作规范
- `interest-capture.md` — 研究方向自动捕获

## 数据布局

```
data/papers/<ULID>/    # 原文 PDF + TeX source
output/parsed/         # 解析后的结构化 JSON (数量取决于已安装 corpus)
output/notes/          # 阅读笔记
output/drafts/         # 写作草稿
output/bib/            # BibTeX
output/experiments/    # 实验代码
output/digests/        # 同步报告
LEAN/                  # Lean4 形式化验证
scholar/               # Python 领域模块
scholar_mcp/           # MCP Server
infra/                 # Docker 配置
```

## 核心约束

- **绝不编造论文、引用、作者、年份**
- **公式必须从 output/parsed/*.json 的 formulas 字段提取**
- **所有学术声明必须有数据支撑**
- **批量操作单条失败不阻塞整批**
