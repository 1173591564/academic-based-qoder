---
name: deep-read
description: "Deep reading and structured analysis of individual papers"
---

## 触发
当用户说"深度阅读 XX 论文"、"帮我分析这篇论文"、"详细读一下 XX"时执行此流程。

## 流程

### Step 0: 预检查
```bash
python -m scholar auto-notes <ULID>
python -m scholar quality-score <ULID>
```
先检查是否已有预生成笔记（`output/notes/<ULID>.md`）和质量评分。
如果已有，基于预生成数据快速开始；如果没有，自动执行 `auto-notes` 生成。

### Step 1: 定位论文
如果用户给出了 paper_id 或 ULID，直接定位。
如果给出的是论文标题，先搜索：
```bash
python -m scholar search "<标题关键词>"
```

### Step 2: 确保已解析
如果论文尚未解析：
```bash
python -m scholar parse <ULID>
```

### Step 3: 全文结构化阅读
读取 `output/parsed/<ULID>.json`，按以下顺序分析：

1. **元数据** — title, authors, year, venue
2. **Abstract** — 快速把握论文定位
3. **Introduction** (sections[0] 通常就是) — 理解动机和贡献声明
4. **Method 部分** — 核心方法论，重点关注 formulas 字段
5. **Experiments** — 实验设置和关键结果
6. **Conclusion** — 局限性声明和未来方向

### Step 4: 提取核心贡献
从论文中识别：
- 提出了什么新方法/新框架/新发现？
- 与现有方法的本质区别是什么？
- 关键的数学创新是什么？（从 formulas 中提取核心公式）
- 方法论的关键假设是什么？（检查 Method 部分的假设声明）

如果论文有分类标签（`tags` 字段），利用它们确认论文所属方向和子领域。

### Step 5: 方法论深度解读
对论文的核心方法，用通俗语言解释：
- 为什么这个方法能 work？
- 关键假设是什么？
- 计算复杂度如何？

### Step 6: 公式解释
从 formulas 字段中选取 3-5 个最重要的公式（优先选有 label 的、长度较长的）：
- 展示原始 LaTeX
- 解释每个符号的含义
- 说明公式在整体方法中的作用
- 检查量纲一致性（如适用）

### Step 6.5: 方法论假设提取
从 Method 部分提取关键假设：
- 数据分布假设（如 i.i.d.、平稳性）
- 模型假设（如线性、可微、凸性）
- 实验假设（如特定数据集的代表性）

### Step 7: 局限性分析
- 论文自己声明的局限性
- 你根据方法论分析出的潜在局限
- 与同领域其他方法相比的不足

### Step 8: 生成阅读笔记
输出到 `output/notes/<paper_id>.md`，结构如下：

```markdown
## <Title>

**Authors:** ...  |  **Year:** ...  |  **Venue:** ...
**Paper ID:** <ULID>

### 一句话总结
<用一句话概括论文的核心贡献>

### 核心贡献
1. ...
2. ...

### 方法概述
<通俗解释核心方法>

### 关键公式
<选取 3-5 个最重要的公式，逐一解释>

### 实验亮点
<关键实验结果>

### 局限性
<分析局限性>

### 与我的研究的关联
<如果是用户研究方向相关的论文，分析潜在关联>
```

## 注意事项
- 如果论文有 Lean4 形式化定义（检查 LEAN/AiEvolution/Database.lean），将其关联起来
- 对比论文时，分别做深度阅读后再对比，不要跳步
