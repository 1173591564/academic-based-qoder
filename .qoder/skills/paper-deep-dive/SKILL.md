---
name: paper-deep-dive
description: "对单篇论文进行全面深度分析：精读、质量评估、公式推导、实验代码"
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

### Step 7: 输出深度分析报告
整合以上分析，生成结构化的深度报告。

## Next Steps

- **`/writing-pipeline`** — 基于深度分析撰写相关学术论文
- **`/reproduce-paper`** — 运行生成的实验代码，验证可复现性
- **`/research-survey`** — 扩展到该论文所在领域的全面调研
