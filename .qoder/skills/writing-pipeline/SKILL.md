---
name: writing-pipeline
description: "端到端学术写作流程：调研→撰写→编译→审稿"
---

## 触发
当用户说"写论文"、"writing"、"帮我写一篇关于 XX 的论文"、"学术写作"时执行此流程。

## 流程

### Step 1: 主题调研
```bash
python -m scholar survey "<topic>" --depth full --limit 20
```
- 双路搜索（RAG + 关键词 + arXiv）
- 生成调研报告 `output/drafts/survey_<topic>.md`

### Step 2: 阅读关键论文笔记
对调研中 Top 5-10 论文，读取预生成笔记：
- `output/notes/<ULID>.md` — 结构化笔记
- `output/notes/<ULID>-quality.json` — 质量评分
优先选择 Grade A/B 的论文作为核心引用。

### Step 3: 撰写 Related Work
基于调研结果撰写相关工作章节：
- 按方法流派分类
- 构建时间线叙事
- 每类引用 2-3 篇代表性论文
- 生成 BibTeX：`python -m scholar export-bib`

### Step 4: 撰写完整论文
按学术论文标准结构撰写：
1. Abstract（200字以内）
2. Introduction（动机 + 贡献 + 结构）
3. Related Work（基于 Step 3）
4. Method（技术方法描述）
5. Experiments（实验设计与结果）
6. Conclusion（总结与展望）
输出 LaTeX 文件到 `output/drafts/`

### Step 5: LaTeX 编译
```bash
python -m scholar compile-paper output/drafts/<file>.tex --auto-fix
```
- 自动修复常见编译错误（缺失包、未定义引用）
- 最多重试 3 次
- 输出 PDF 到 `output/pdfs/`

### Step 6: 自审报告
对生成的论文进行自审：
- 逻辑完整性检查
- 引用一致性检查
- 格式规范性检查
- 输出审稿报告

## Next Steps

- **`/reproduce-paper`** — 复现论文中的实验
- **`/paper-deep-dive`** — 对引用论文做深度分析
- **`/idea-to-paper`** — 从新点子出发端到端写论文
