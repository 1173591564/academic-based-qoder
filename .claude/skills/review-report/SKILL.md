---
name: review-report
description: "撰写结构化同行评审报告，含评分与改进建议"
output_contract:
  path: output/notes/
  format: markdown
  required_fields:
    - paper_id
    - scores
    - recommendations
  citation_check: false
---

## 触发
当用户说"帮我审稿"、"写 review"、"评审这篇论文"、"peer review"时执行此流程。

## 流程

### Step 1: 定位并深度阅读论文
先检查预生成数据：
```bash
python -m scholar quality-score <ULID>
python -m scholar info <ULID>
```
- 读取预生成笔记：`output/notes/<ULID>.md`
- 读取质量评分：`output/notes/<ULID>-quality.json`（7 维度自动评分）
- 读取完整 JSON：`output/parsed/<ULID>.json`

预生成的质量评分可作为审稿参考，但不能代替你自己的深度分析。

### Step 2: 评估论文贡献
- **新颖性**：提出了什么新方法/新发现？与现有工作的本质区别是什么？
- **重要性**：这个问题有多重要？解决后对领域有多大影响？
- **完整性**：论文是否完整地呈现了研究？是否有遗漏的关键实验或分析？

### Step 3: 方法论审查
- **假设合理性**：核心假设是否有理论或实验支撑？
- **数学正确性**：公式推导是否有错误？（如需要可执行 paper-deep-dive 流程的 Step 4 公式推导）
- **方法对比**：与 baseline 方法的对比是否公平？
- **消融实验**：是否验证了各组件的独立贡献？

### Step 4: 实验审查
- **数据集选择**：是否使用了标准 benchmark？
- **评估指标**：指标选择是否合适？
- **统计显著性**：是否报告了误差范围/置信区间？
- **可复现性**：实验细节是否足够详细？

### Step 5: 写作质量审查
- **结构清晰度**：论文组织是否合理？
- **图表质量**：图表是否清晰传达信息？
- **引用完整性**：是否遗漏了重要相关工作？
- **语言质量**：是否有表达不清或语法错误？

### Step 6: 对照引用网络
```bash
python -m scholar cite-network <ULID>
```
查看：
- 这篇论文引用了哪些工作？引用是否准确？
- 是否有重要的前置工作被遗漏？

### Step 7: Lean4 形式化对照（如适用）
如果论文方法在 AiEvolution 中有形式化定义，验证核心声明是否与形式化一致。

### Step 8: 输出审稿报告
输出到 `output/notes/review-<paper_id>.md`：

```markdown
## 审稿报告: <title>

**Paper ID:** <ULID>
**Authors:** <authors>
**Venue:** <venue> (<year>)

### Summary
<用 3-5 句话概述论文的贡献和方法>

### Strengths
1. <优点1>
2. <优点2>
3. ...

### Weaknesses
1. <缺点1>
2. <缺点2>
3. ...

### Questions for Authors
1. <需要作者澄清的问题>
2. ...

### Minor Issues
- <小问题列表>

### Overall Assessment
- **Novelty:** X/5
- **Significance:** X/5
- **Technical Quality:** X/5
- **Clarity:** X/5
- **Overall:** X/5

### Recommendation
Accept / Weak Accept / Borderline / Weak Reject / Reject

### Confidential Remarks (可选)
<仅对编辑可见的评论>
```

## 注意事项
- 审稿要客观公正，基于论文的实际内容
- 批评要建设性，每个缺点都应附带改进建议
- 不要基于个人偏好而打分
- 如果发现论文有重大错误（如数学推导错误），要重点指出

## Next Steps

审稿报告完成后，自然的后续动作：

- `python -m scholar quality-score <ULID>` — 如果审稿中发现问题，用质量评分做量化记录
- **`/paper-deep-dive`** — 对审稿中引用的对比论文做精读，补充审稿论据
- `python -m scholar export-bib` — 导出审稿涉及的所有引用

> 传递数据：审稿报告中的「主要问题」和「改进建议」可用于指导后续论文修改或对比分析。
