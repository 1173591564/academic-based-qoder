# Scholar Studio Plugin

> 需要配合主仓库使用：https://gitee.com/gu-yulong1217317/academic-based-qoder

## 包含能力

| 类型 | 数量 | 说明 |
|------|------|------|
| Skills | 22 | 18 原子 + 4 组合 Workflow |
| Commands | 4 | stats / find / paper / health |
| MCP Server | 1 | Scholar MCP（29 工具） |

## 前置要求

```bash
# 1. 克隆主仓库
git clone https://gitee.com/gu-yulong1217317/academic-based-qoder.git
cd academic-based-qoder

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动数据库
./startup.ps1

# 4. 全量初始化
python -m scholar bootstrap
```

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
