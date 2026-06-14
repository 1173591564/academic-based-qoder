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

### Step 3: 生成论文大纲
基于调研结果，先构建论文结构大纲：
- 确定各 section 的核心论点和篇幅分配
- 为每个 section 标注关键引用 paper_id
- 生成 BibTeX：`python -m scholar export-bib`
- 输出大纲到 `output/drafts/<topic>-outline.md`

### Step 4: 逐节撰写初稿
按 section 逐步撰写 LaTeX，**每个 section 单独写入并检查**：

1. **Related Work**：按方法流派分类 + 时间线叙事，每类引用 2-3 篇代表论文
2. **Introduction**：动机 → 贡献 → 论文结构（写于 Related Work 之后，确保引用一致）
3. **Method**：技术方法描述，公式从 JSON formulas 字段提取
4. **Experiments**：实验设计与结果
5. **Conclusion**：总结与展望
6. **Abstract**：最后写，200 字以内，概括全文

每个 section 写完后：
- 检查引用的 paper_id 是否都存在于知识库
- 回顾前文，确保逻辑连贯、术语一致
- 输出 LaTeX 文件到 `output/drafts/`

### Step 5: 质量门控
对初稿执行多维度质量检查：
- **引用准确性**：所有 `\cite{}` 是否对应真实 paper_id？参考文献列表是否完整？
- **论证连贯**：Introduction 承诺的贡献是否在 Method/Experiments 中得到兑现？
- **篇幅均衡**：各 section 字数比例是否合理？（如 Method 不应远短于 Related Work）
- **Abstract 独立性**：Abstract 是否能脱离全文独立理解？

生成修改清单 `output/drafts/<topic>-review.md`：
- `[PASS]` 通过的检查项
- `[REVISE]` 需要修改的项，列出具体问题和位置
- `[MISSING]` 缺失内容（如"缺少消融实验描述"）

### Step 6: 定向修订
根据质量门控结果执行修改：
- 对 `[REVISE]` 项：针对性修改对应段落
- 对 `[MISSING]` 项：补充内容，必要时回到 `python -m scholar search` 补数据
- **最多 2 轮修订**，每轮后重新检查未通过项
- 全部通过或 2 轮后强制通过

### Step 7: LaTeX 编译与错误修复

执行「编译→诊断→修复」闭环，直到 PDF 生成且无 FATAL 错误。

#### 7a. 编译
```bash
python -m scholar compile-paper output/drafts/<file>.tex
```
- 英文版使用 `pdflatex`，中文版使用 `xelatex`
- 双遍编译以解析交叉引用和引用
- CLI 自动输出结构化错误报告（按 FATAL/WARN/INFO 分类）

#### 7b. 日志诊断
读取编译日志 `output/drafts/<file>.log`，按严重级别分类：
- **`[FATAL]`** PDF 未生成 — 缺失包、语法错误、未定义命令
- **`[WARN]`** PDF 已生成但有缺陷 — Overfull/Underfull、未定义引用
- **`[INFO]`** 字体/编码警告 — 可忽略

如果 CLI 输出了结构化报告，直接使用；否则手动解析 .log 文件。

#### 7c. 自动修复策略

按优先级处理：先修 FATAL（必须），再修 WARN（尽量）。

| 错误模式 | 日志特征 | 修复动作 |
|----------|----------|----------|
| 缺失包 | `File xxx.sty not found` | 导言区添加 `\usepackage{xxx}` |
| 未定义命令 | `Undefined control sequence` + `\xxx` | 识别命令来源，添加对应包或 `\newcommand` |
| 缺失 `$` | `Missing $ inserted` | 定位源文件行号，补上数学模式分隔符 |
| 未定义引用 | `Citation 'xxx' undefined` | `python -m scholar search "xxx"` 验证 paper_id，补 .bib 条目 |
| 未定义标签 | `Reference 'xxx' undefined` | 检查 `\label`/`\ref` 对应关系，修正拼写 |
| 公式溢出 | `Overfull \hbox (Xpt too wide)` 在 equation 环境 | 添加 `split` 换行或 `\resizebox{\linewidth}{!}{...}` |
| 表格溢出 | 同上，在 table 环境内 | 添加 `\resizebox{\columnwidth}{!}{...}` |
| 段落溢出 | 同上，含 `\texttt` 的段落 | 局部 `{\emergencystretch=20pt ... \par}` + `\allowbreak` |
| 编码错误 | `Invalid UTF-8` | 修正特殊字符为合法 LaTeX 转义 |

#### 7d. 重编译循环
- 每轮修复后重新编译（双遍）
- **最多 3 轮**：FATAL 必须清零，WARN 尽量清零
- 每轮记录修复内容到 `output/drafts/<topic>-compile-log.md`：
  ```markdown
  ## 编译修复日志
  ### 第 1 轮
  - FATAL: 3 → 0（修复：添加 \usepackage{booktabs}, \usepackage{amssymb}）
  - WARN: 5 → 2（修复：2 个 Overfull 添加 split，1 个 undefined cite）
  ### 第 2 轮
  - WARN: 2 → 0（修复：resizebox 缩放 tab:comp 表格）
  ```

#### 7e. 编译报告
编译成功后输出最终状态：
- PDF 路径、页数、文件大小
- Overfull/Underfull 最终计数
- 残余警告列表（如有）
- 修复日志路径

将 PDF 复制到 `output/pdfs/`，清理 .aux/.log/.out 中间文件。

## 迭代写入原则
- 大纲先行，确保全局结构合理再开始写正文
- 逐节撰写，每个 section 写完即检查，不等到全文完成才发现问题
- Abstract 最后写，确保概括了最终定稿的全部内容
- 质量门控是强制环节，不允许跳过
- **编译修复是闭环**：不允许跳过编译，不允许忽略 FATAL 错误

## Next Steps

- **`/reproduce-paper`** — 复现论文中的实验
- **`/paper-deep-dive`** — 对引用论文做深度分析
- **`/idea-to-paper`** — 从新点子出发端到端写论文
