---
name: paper-compare
description: "Compare multiple papers on methods, experiments, and evolution"
---

## 触发
当用户说"对比这几篇论文"、"比较 XX 和 YY"、"分析这些方法的区别"时执行此流程。

## 流程

### Step 0: 预检查
对每篇目标论文，检查预生成数据：
```bash
python -m scholar auto-notes <ULID>
```
- 阅读笔记：`output/notes/<ULID>.md`（摘要、贡献、方法、公式）
- 质量评分：`output/notes/<ULID>-quality.json`（7维度评分对比）
- 分类标签：`output/parsed/<ULID>.json` 的 `tags` 字段

### Step 1: 定位论文集合
用户可能给出：
- 具体论文名称/paper_id → 直接定位
- 一个研究方向 → 先搜索，选取 3-5 篇代表性论文

### Step 2: 逐篇深度阅读
对每篇论文，优先读取预生成笔记（`output/notes/<ULID>.md`），然后补充读取完整 JSON：
- 核心方法
- 关键公式
- 实验设置

### Step 2.5: 引用关系自动检测
```bash
python -m scholar cite-network <ULID>
```
检查论文之间是否存在互引关系（CITES 边）。
如果 Neo4j 已构建，用 `graph-query` 检查是否有共同概念。

### Step 3: 交叉分析
比较维度：
- **方法论**：核心思路有何异同？数学形式有何区别？
- **实验**：在哪些 benchmark 上对比过？结果如何？
- **适用场景**：各自的优势场景是什么？
- **演进关系**：后发表的论文是否引用/改进了前面的？

检查 citations 字段确认引用关系。

### Step 4: 生成对比表格
利用预生成数据快速填充对比表格：

| 维度 | Paper A | Paper B | Paper C |
|------|---------|---------|----------|
| 核心方法 | ... | ... | ... |
| 关键公式 | ... | ... | ... |
| 数据集 | ... | ... | ... |
| 主要结论 | ... | ... | ... |
| 局限性 | ... | ... | ... |
| 质量评分 | A/B/C | A/B/C | A/B/C |

### Step 5: 构建演进脉络
如果论文之间有引用关系，画出演进脉络：
```
Paper A (2020) → Paper B (2022) → Paper C (2024)
         ↘ Paper D (2023)
```

### Step 6: 输出
输出到 `output/drafts/compare-<topic>.md`。

## 注意事项
- 对比要基于论文的实际内容（parsed JSON），不要凭印象
- 公式对比时，尽量用统一的数学符号
- 如果某篇论文有 Lean4 形式化定义，将其属性（scalability/simplicity/stability）纳入对比

## Next Steps

对比完成后，自然的后续动作：

- **`/related-work`** — 基于对比结果，撰写 Related Work 章节
- **`/concept-evolution`** — 追踪对比中涉及的概念之间的替代/演化关系
- **`/research-gap`** — 从方法差异中发现尚未解决的问题

> 传递数据：对比报告 `output/drafts/compare-<topic>.md` 中的方法对比表可直接嵌入 Related Work。
