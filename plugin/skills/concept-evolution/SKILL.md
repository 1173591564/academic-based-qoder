---
name: concept-evolution
description: "追踪概念演化、技术替代链和范式变迁"
---

## 触发
当用户说"追踪概念演化"、"XX 是怎么发展来的"、"技术替代"、"概念时间线"、"演化脉络"时执行此流程。

## 前置条件
Neo4j 概念图谱已构建：`python -m scholar graph-build`

## 流程

### Step 1: 确定追踪目标
用户可能给出：
- 一个具体概念（如 "Transformer", "GAN", "RLHF"）
- 一个研究方向（如 "生成模型", "强化学习"）
- 要求全局演化概览

### Step 2: 概念图谱查询
```bash
python -m scholar graph-query <概念ID>
python -m scholar graph-stats
```
获取：
- 该概念关联的所有论文（按年份排序）
- 与该概念共现的相关概念（RELATED_TO 边权重）
- 概念的时间分布
- TF-IDF 提取的概念相关性（通过 classify 标签辅助）

### Step 3: 替代关系追踪
从 Neo4j REPLACES 边和 Lean4 Database.lean 提取替代关系：
```bash
python -m scholar graph-stats
```
在 Neo4j 中查询：`MATCH (a:Innovation)-[:REPLACES]->(b:Innovation) RETURN a.id, b.id`
已知的替代链（如 GAN → Diffusion, RNN → Transformer, PPO → DPO）。
对每条替代关系：
- 找到"被替代者"的代表论文
- 找到"替代者"的代表论文
- 找到过渡期间的关键论文

### Step 4: 时间线构建
结合论文年份和引用关系，构建概念的时间演化线：
```bash
python -m scholar list-papers --year <Y>
```
对每个关键年份：
- 哪些论文引入了新概念？
- 哪些论文改进了已有概念？
- 哪些论文标志着概念的成熟/衰退？

### Step 5: 引用路径分析
如果 Neo4j 可用，查找概念之间的引用路径：
```bash
python -m scholar cite-network <ULID>
```
分析：
- 旧概念的论文是否引用了新概念的论文？（抵抗 vs 接受）
- 新概念是否引用了旧概念？（继承 vs 断裂）
- 桥接论文在演化中扮演什么角色？

### Step 6: Lean4 定理验证
检查 AiEvolution 中的演化定理：
```bash
cd LEAN && lake build AiEvolution
```
已证明的定理（如 `transformer_replaces_rnn`）提供了形式化的演化证据。

### Step 7: 输出
输出到 `output/drafts/evolution-<concept>.md`：

```markdown
## 概念演化: <concept>

### 概念定义
<概念的核心定义和在 AI 领域的位置>

### 演化时间线
| 年份 | 事件 | 代表论文 | 类型 |
|------|------|---------|------|
| 2014 | GAN 提出 | Goodfellow et al. | 创生 |
| 2018 | StyleGAN | Karras et al. | 改进 |
| 2020 | Diffusion 崛起 | Ho et al. | 替代 |
| 2023 | ... | ... | ... |

### 替代关系
```
GAN (2014) ──[被 Diffusion 替代 2020]──> Diffusion Models
                                              │
                                              └──[改进]──> Latent Diffusion (2022)
```

### 关键论文分析
<对演化中的关键论文做简要分析>

### 当前状态
<概念当前的研究活跃度和未来趋势>

### Lean4 形式化证据
<如果 AiEvolution 中有相关定理，列出>
```

## 注意事项
- 演化分析要基于引用数据和论文内容，不要仅凭印象
- 替代关系是强声明，需要充分证据（Lean4 定理 > 引用数据 > 定性分析）
- 概念的"死亡"很难判断，谨慎使用"已被取代"这类表述
- 区分"概念消亡"和"概念融入更大框架"

## Next Steps

概念演化分析完成后，自然的后续动作：

- **`/research-gap`** — 从演化链的末端发现尚未探索的方向
- **`/citation-network`** — 深入分析替代关系（REPLACES 边）的引用证据
- **`/paper-recommendation`** — 推荐当前「最前沿」概念的论文

> 传递数据：演化链中的「当前主流技术」和「被替代技术」可直接用于 research-gap 分析。
