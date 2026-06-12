---
name: idea-to-paper
description: "从研究点子到完整论文的端到端流程：调研→写作→复现→成文"
---

## 触发
当用户说"我有一个想法"、"帮我实现这个点子"、"idea to paper"、"从想法到论文"时执行此流程。

## 流程

### Step 1: 点子明确化
与用户讨论，明确：
- 核心创新点是什么
- 要解决什么问题
- 预期贡献（理论/方法/应用）
- 目标投稿会议/期刊

### Step 2: 文献调研
```bash
python -m scholar survey "<topic>" --depth full --limit 25
```
- 搜索与点子相关的已有工作
- 确认 novelty（是否有类似工作）
- 识别关键参考文献
- 生成调研报告

### Step 3: 研究 Gap 分析
基于调研报告分析：
- 已有方法的局限性
- 本方法相比已有工作的优势
- 潜在的实验对比基线

### Step 4: 方法设计
将点子转化为具体的技术方案：
- 算法框架设计
- 数学公式推导
- 关键模块定义

### Step 5: 实验设计
- 选择基准方法（从调研中识别）
- 确定评估指标
- 选择数据集
- 设计消融实验

### Step 6: 代码实现与实验
```bash
python -m scholar exp-setup <baseline_paper_id> --conda
python -m scholar exp-run <paper_id> --mode quick
python -m scholar exp-compare <paper_id>
```
- 实现提出的方法
- 运行快速验证实验
- 与基线方法对比

### Step 7: 论文撰写
```bash
# 自动触发 /writing-pipeline 流程
```
- 撰写完整 LaTeX 论文
- 包含实验结果和对比表格
- LaTeX 编译为 PDF

### Step 8: 自审与修改
- 逻辑完整性检查
- 实验结果一致性
- 引用准确性验证
- 输出修改建议

## Next Steps

完成端到端流程后：
- 根据自审报告修改完善
- 准备投稿材料
- 扩展实验（full mode）
