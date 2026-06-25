---
name: paper-deep-dive
description: "对单篇论文进行全面深度分析：精读、质量评估、公式推导、实验代码"
output_contract:
  path: output/notes/
  format: markdown
  required_fields:
    - paper_id
    - title
    - analysis
  citation_check: true
---

## 触发
当用户说"精读 XX"、"深度分析 XX"、"分析这篇论文"、"彻底搞懂 XX"时执行此流程。

## 流程

### Step 1: 加载论文数据
```bash
python -m scholar info <paper_id>
```
- 支持 Hybrid ID：ULID / arXiv ID / DOI / slug 均可
- 读取预生成数据：`output/parsed/<ULID>.json`、`output/notes/<ULID>.md`

### Step 2: 深度阅读
阅读论文 JSON 全文（sections、formulas、citations），提取：
- 核心贡献和创新点
- 关键算法和数学公式
- 实验设计和结果
- 局限性

### Step 3: 质量评估
```bash
python -m scholar quality-score <paper_id>
```
展示 7 维度评分（metadata / structure / citations / reproducibility / problem / innovation / experiments）。

### Step 4: 公式推导
对论文中的关键公式进行逐步推导：
- 展开省略的中间步骤
- 验证数学正确性
- 解释物理/直觉含义

### Step 5: 引用网络分析
```bash
python -m scholar cite-network <paper_id>
```
展示前向引用（本文引用了谁）和后向引用（谁引用了本文）。

### Step 6: 生成实验代码框架
基于论文描述的算法，生成可运行的实验代码结构：
- 确定技术栈（PyTorch / TensorFlow / JAX）
- 提取算法伪代码
- 生成模块化的代码文件
- 输出到 `output/experiments/<ULID>/`

### Step 7: 质量门控
在生成最终报告前，验证分析质量：
- **数据支撑**：每个分析声明是否有论文 JSON 中的实际内容支撑？
- **公式一致性**：推导结果与论文原始公式是否一致？有无跳步或错误？
- **引用完整性**：引用网络分析是否覆盖前后向引用？
- **评估全面性**：7 维度质量评分是否每个维度都有具体评价？

生成修改清单：
- `[PASS]` 分析充分的 section → 保留
- `[REVISE]` 需要加强的部分 → 列出具体问题
- `[MISSING]` 缺失分析 → 需要回到 Step 2 重新阅读

### Step 8: 增量撰写深度报告
整合以上分析，**按 section 逐步撰写**，每写完一个 section 回顾已写内容：

1. **核心贡献总结**：一句话概括论文本质创新
2. **方法深度分析**：算法框架 + 关键公式推导
3. **质量评估详述**：7 维度评分及理由
4. **引用网络位置**：本文在领域中的定位
5. **实验代码概要**：实现思路和技术栈选择

根据质量门控的 `[REVISE]` 项做定向修改，`[MISSING]` 项补充分析。**最多 2 轮修订**。输出到 `output/notes/<ULID>-deep-dive.md`。

## 迭代分析原则
- 每个分析声明必须能指向论文 JSON 中的具体证据
- 质量门控是强制环节，确保不放过错误分析
- 报告按 section 增量撰写，后续 section 可以修正前面的理解
- 最多 2 轮修订，避免过度分析

## Next Steps

- **`/writing-pipeline`** — 基于深度分析撰写相关学术论文
- **`/reproduce-paper`** — 运行生成的实验代码，验证可复现性
- **`/research-survey`** — 扩展到该论文所在领域的全面调研
