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

### Step 7: 论文大纲与结构验证
基于调研、Gap 分析和实验结果，构建论文大纲：
- 确定各 section 的核心论点和篇幅分配
- 验证结构完整性：问题→方法→实验→结论是否形成闭环
- 为每个 section 标注关键引用 paper_id
- 输出大纲到 `output/drafts/<topic>-outline.md`

### Step 8: 逐节撰写初稿
按 section 逐步撰写 LaTeX，**每个 section 单独写入并检查**：

1. **Related Work**：基于调研结果，按流派分类 + 时间线叙事
2. **Introduction**：动机 → 贡献 → 结构
3. **Method**：方法设计 + 数学推导 + 算法描述
4. **Experiments**：实验结果 + 对比表格 + 消融实验
5. **Conclusion**：总结与展望
6. **Abstract**：最后写，概括全文

每个 section 写完后检查引用一致性和逻辑连贯性。输出 LaTeX 文件到 `output/drafts/`。

### Step 9: 质量门控
对初稿执行多维度检查：
- **实验一致性**：实验结果是否与 Step 6 的实验数据一致？
- **引用准确性**：所有引用 paper_id 是否存在于知识库？
- **论证链条**：Introduction → Method → Experiments → Conclusion 是否逻辑闭环？
- **篇幅均衡**：各 section 字数比例是否合理？

生成修改清单：
- `[PASS]` 通过的 section
- `[REVISE]` 需要修改的项
- `[MISSING]` 缺失内容

### Step 10: 定向修订与终稿
根据质量门控结果执行修改：
- 对 `[REVISE]` 项：针对性修改
- 对 `[MISSING]` 项：补充内容
- **最多 2 轮修订**，每轮后重新检查
- 全部通过后，按 `writing-pipeline` Step 7 的「编译→诊断→修复」协议编译为 PDF：
  - 运行 `python -m scholar compile-paper output/drafts/<file>.tex`
  - 解析 .log 按 FATAL/WARN/INFO 分类
  - 自动修复（缺失包、溢出、未定义引用等），最多 3 轮
  - FATAL 必须清零，WARN 尽量清零

## 迭代写入原则
- 大纲先行，验证结构闭环后再写正文
- 逐节撰写，每个 section 写完即检查
- Abstract 最后写，确保概括最终定稿
- 质量门控是强制环节，最多 2 轮修订
- **编译修复是闭环**：不允许跳过编译，不允许忽略 FATAL 错误

## Next Steps

完成端到端流程后：
- 准备投稿材料
- 扩展实验（full mode）
- **`/research-survey`** — 补充更多相关文献

> 传递数据：论文终稿、实验代码、调研报告均可用于后续投稿和扩展。
