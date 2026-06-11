---
name: related-work
description: "撰写带规范引用和叙事结构的 Related Work 章节"
---

## 触发
当用户说"帮我写 Related Work"、"写文献综述"、"帮我整理引用"时执行此流程。

## 前置条件
本地知识库已有解析数据（parsed/*.json）。如果为空，先执行 research-survey 建库。

## 流程

### Step 1: 确定写作范围
与用户确认：
- 研究方向/论文主题是什么？
- Related Work 需要覆盖哪些子领域？
- 大概需要引用多少篇论文？
- 输出格式：Markdown 还是 LaTeX？

### Step 2: 检索相关论文（双路搜索）
```bash
python -m scholar search "<子领域1>"
python -m scholar rag-search "<子领域1>" --hybrid
python -m scholar classify --list-tags
```
- 关键词搜索：精确匹配
- RAG 混合搜索：语义相似度 + BM25，发现隐含相关的论文
- 分类标签：利用 `tags` 字段按方向过滤
对每个子领域搜索，收集相关论文列表。

### Step 3: 阅读摘要和核心贡献
对检索到的论文，利用预生成数据快速阅读：
- 阅读笔记：`output/notes/<ULID>.md`（一句话摘要 + 核心贡献）
- 质量评分：`output/notes/<ULID>-quality.json`（帮助判断论文质量）
- 完整 JSON 的 abstract 和 sections（重点看 Introduction）
提取：
- 每篇论文的核心贡献（一句话）
- 与目标研究方向的关联（是前置工作、对比方法、还是应用领域）

### Step 4: 构建大纲
按主题分组，构建 Related Work 大纲：
```
2. Related Work
  2.1 <子领域1> (N篇论文)
  2.2 <子领域2> (N篇论文)
  2.3 <与本研究最相关的工作> (N篇论文)
```

### Step 5: 逐节撰写
每个子节遵循模式：
- 先概述这个子领域的研究脉络
- 按时间或方法分类介绍代表性工作
- 指出每篇工作的关键贡献和局限
- 最后总结这些工作与本研究的关系

### Step 6: 插入引用
LaTeX 格式使用 `\cite{paper_id}`。
Markdown 格式使用 `[paper_id]`。

### Step 7: 生成 BibTeX
```bash
python -m scholar export-bib
```
确保所有引用的论文都有对应的 BibTeX 条目。

### Step 8: 输出
输出到 `output/drafts/related-work-<topic>.md` 或 `.tex`。

### Step 9: 自检
- 检查是否遗漏了重要相关工作（搜索遗漏的子领域）
- 检查引用的准确性（确保 paper_id 对应正确的论文）
- 检查叙事逻辑（各子节之间是否有连贯的过渡）
- 如有 Lean4 对应的形式化定义，在引用中标注

## 注意事项
- 永远不要编造不存在的引用！如果不确定，先搜索确认
- 每篇被引用的论文，至少读取其 abstract 后再写
- Related Work 不是简单的论文列表，需要有分析和综合

## Next Steps

Related Work 写完后，自然的后续动作：

- **`/bibtex-management`** — 导出引用论文的 BibTeX 文件
- **`/review-report`** — 对自己写的内容做审稿式审查
- **`/paper-compare`** — 补充更多论文对比细节

> 传递数据：LaTeX 草稿中的 `\cite{}` 引用列表可直接用于 BibTeX 导出。
