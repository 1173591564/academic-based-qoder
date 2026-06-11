---
name: math-verification
description: "数学公式与定理验证，支持 Lean4 形式化"
---

## 触发
当用户说"验证这个公式"、"检查数学推导"、"形式化验证"、"这个定理对吗"时执行此流程。

## 前置条件
Lean4 已安装在本地，AiEvolution 项目在 `LEAN/` 目录下。

## 流程

### Step 1: 定位目标公式
用户可能给出：
- 某篇论文中的具体公式 → 从 `output/parsed/<ULID>.json` 的 formulas 字段提取
- 一个数学命题 → 先确认其出处论文
- Lean4 中已有的定义 → 直接查看 `LEAN/AiEvolution/` 文件

### Step 2: 提取公式上下文
读取论文 JSON，找到公式所在的章节和前后文：
- 公式的 LaTeX 源码（formulas 字段的 latex 值）
- 公式在论文中的位置（哪个 section）
- 公式周围的文字说明（定义、假设、证明思路）

### Step 3: 语义分析
对公式进行语义分析：
- 识别公式中每个符号的含义（从上下文推断）
- 检查公式的维度一致性（矩阵/向量维度是否匹配）
- 检查极限情况是否合理（如 n→0, n→∞ 时公式是否退化到已知形式）
- 检查不等式方向是否正确
- 检查特殊值代入是否成立（如 x=0, x=1）

### Step 4: 对照 Lean4 已有定义
检查 Neo4j 中是否有相关 Innovation 节点：
```bash
python -m scholar graph-query <概念名>
```
检查 Lean4 项目中是否已有相关形式化：
```bash
cd LEAN && grep -r "关键词" AiEvolution/
```
已有的形式化包括：
- `Basic.lean`: 类型定义 (Innovation, Paper, ResearchLine)
- `Database.lean`: 125 个创新节点、440 篇论文、引用关系、替代关系
- `Theorems.lean`: 已证明的演化定理（7 个定理，无 sorry）

### Step 5: 形式化尝试（如适用）
如果公式适合形式化，尝试在 Lean4 中编写：
1. 定义相关类型和变量
2. 用 Lean4 语法表述定理
3. 尝试证明（简单的可以用 `simp`, `ring`, `linarith` 等策略）

将尝试结果写入 `output/notes/math-verify-<paper_id>.md`。

### Step 6: 编译验证
```bash
cd LEAN && lake build AiEvolution
```
检查编译是否通过。如果失败，分析错误原因并记录。

### Step 7: 生成验证报告
输出到 `output/notes/math-verify-<formula_label>.md`：

```markdown
## 公式验证: <label>

**论文:** <title> (<year>)
**公式:** <LaTeX>

### 语义分析
- 符号说明
- 维度检查
- 极限情况

### 验证结果
- [ ] 语义一致性
- [ ] 维度一致性
- [ ] 极限退化
- [ ] Lean4 形式化
- [ ] 编译通过

### 备注
<分析备注>
```

## 注意事项
- 并非所有公式都适合形式化验证，复杂深度学习公式可能只能用语义分析
- Lean4 验证的覆盖范围有限，重点是 AI 演化相关的核心定理
- 不要声称"已证明"除非 Lean4 编译确实通过
- 对于验证失败的公式，明确记录失败原因

## Next Steps

数学验证完成后，自然的后续动作：

- **`/formula-derivation`** — 对验证通过（或失败）的公式做进一步推导
- **`/deep-read`** — 回读论文确认形式化结果与原文的一致性
- **`/experiment-code`** — 如果公式涉及算法，实现对应的实验代码

> 传递数据：Lean4 验证结果（通过/失败）和定理定义可直接用于论文写作中的形式化引用。
