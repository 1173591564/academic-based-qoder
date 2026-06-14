# Adaptive Research Loop 实现方案

## 设计原则

- **组合式创新**：复用 `kb_update.py` 的 arXiv 搜索/下载/入库管线，不重写已有逻辑
- **Qoder Work 原生集成**：定时任务用 Scheduled Tasks，推送用 IM Channels，零代码
- **软硬约束协同**：Hook 做无脑记录（硬约束），Agent 做语义分析（软约束），两层解耦
- **渐进式迭代**：MVP 可在 2-3 小时内构建并测试，后续逐步增强

### 架构概览

```
用户每条消息 ──→ Stop Hook ──→ week-YYYY-WNN.jsonl（原始日志，硬约束）
                                        ↓
                              定时任务触发（每周一次）
                                        ↓
                              Agent 读日志 + Rule 引导语义分析
                                        ↓
                              提取出 N 个研究方向
                                        ↓
                              IM 推送方向列表 → 用户确认方向
                                        ↓
                              确认的方向 → 搜索 arXiv → 下载 → 全流程入库
```

**核心设计**

| 原则 | 说明 |
|------|------|
| 方向级确认 | 用户决定的是「追踪哪个方向」，不是「挑哪几篇论文」 |
| 一条龙执行 | 方向确认后，搜索→下载→解析→图谱→RAG→笔记 全自动完成 |
| 单任务闭环 | 一个定时任务搞定：提取兴趣→推送→用户确认→执行 |
| 软硬约束协同 | Hook 做无脑记录（硬约束），Agent 做语义分析（软约束） |

---

## Task 0: Hook 驱动的对话日志采集 [NEW FILE + MODIFY]

**设计理念**：用户不会主动声明兴趣，也不会说「今天就到这里」。Hook 在每次对话结束时自动记录用户消息，作为兴趣分析的原始数据。日志只做无脑记录，不做语义判断——语义分析交给后续的定时任务。

### 0.1 新建 Hook 脚本 `.qoder/hooks/log-conversation.ps1` [NEW FILE]

触发事件：`Stop`（Agent 完成响应时）

```powershell
# 1. 从 stdin 读取 JSON 上下文
# 2. 提取 user_messages 中的文本内容
# 3. 计算当前 ISO 周编号（如 W24）
# 4. 追加写入 output/logs/week-2026-W24.jsonl（一行一条 JSON）
# 格式：{"ts": "2026-06-14T10:30:00", "session": "xxx", "text": "用户消息摘要"}
# 5. exit 0（不阻断 Stop 事件）
```

**关键约束**：
- 只记录用户消息，不记录 Agent 响应（减少噪音）
- 单行 JSONL 格式，支持 `tail -n` 和流式读取
- **按周轮转**：文件名为 `output/logs/week-YYYY-WNN.jsonl`（ISO 周编号）
- 一周一个文件，与定时分析周期对齐，分析完即标记完成
- 如果日志目录不存在，自动创建

### 0.1b 日志完成状态文件 `output/logs/analyzed.json` [NEW FILE]

记录哪些周的日志已经完成分析，由定时任务中的 Agent 写入：

```json
{
  "2026-W24": {"analyzed_at": "2026-06-21T09:00:00", "interests_found": 3, "entries": 47},
  "2026-W25": {"analyzed_at": "2026-06-28T09:00:00", "interests_found": 1, "entries": 22}
}
```

**流程**：
1. Hook 每次写入当前周的 log 文件（`week-2026-W24.jsonl`）
2. 定时任务触发时，Agent 查 `analyzed.json`，找到所有 `week-*.jsonl` 文件中尚未标记的周
3. 读取该周 log，分析提取兴趣
4. 写入 `analyzed.json` 标记该周为已完成
5. 下周的日志自动进入新的 `week-2026-W25.jsonl`

### 0.2 修改 `.qoder/hooks/hooks.json` [MODIFY]

在现有 `Stop` hooks 数组中追加 log-conversation hook：
```json
{
  "type": "command",
  "command": "powershell.exe -ExecutionPolicy Bypass -File \"${QODER_PLUGIN_ROOT}/hooks/log-conversation.ps1\""
}
```

---

## Task 1: 创建核心模块 `scholar/research_loop.py` [NEW FILE]

新建 `scholar/research_loop.py`（~280 行），实现 8 个核心函数：

### 1.1 兴趣管理函数

```python
def load_interests() -> dict:
    """读取 output/research-interests.json，不存在则返回空模板。"""

def save_interests(data: dict) -> None:
    """原子写入兴趣文件（先写 .tmp 再 os.replace）。"""

def add_interest(keywords: str, category: str = "general", max_results: int = 10) -> dict:
    """添加兴趣条目。keywords 为逗号分隔字符串。自动去重。"""

def remove_interest(category: str) -> dict:
    """按 category 删除兴趣条目。"""
```

### 1.1b 日志分析函数（供定时任务中的 Agent 调用）

```python
def get_unanalyzed_logs() -> tuple[Path, list[dict]]:
    """找到最近一个未分析的周日志文件，返回其内容。
    
    逻辑：
    1. 扫描 output/logs/week-*.jsonl 获取所有周文件
    2. 读取 output/logs/analyzed.json 获取已完成列表
    3. 差集 = 未分析的周（取最早的一周）
    4. 读取该文件所有行，解析为 dict 列表
    
    返回: (week_file_path, [{"ts": "...", "session": "...", "text": "..."}, ...])
    """

def mark_week_analyzed(week_id: str, interests_found: int, entries: int) -> None:
    """标记某周日志已完成分析，写入 analyzed.json。
    
    week_id: ISO 周编号，如 "2026-W24"
    """
```

**兴趣文件格式** (`output/research-interests.json`)：
```json
{
  "version": 1,
  "updated_at": "2026-06-14T10:30:00",
  "interests": [
    {
      "category": "LLM Efficiency",
      "keywords": "mixture of experts, sparse attention",
      "max_results": 10,
      "added_at": "2026-06-14",
      "search_count": 0,
      "last_searched": null
    }
  ],
  "history": []
}
```

#### 1.2 方向级入库函数（核心：确认方向后一条龙执行）

```python
def sync_direction(category: str, max_results: int = 10) -> dict:
    """对一个已确认的研究方向执行完整管线：搜索→下载→入库。

    流程:
    1. load_interests() 获取该 category 的关键词
    2. 对每个 keyword 调用 config.arxiv_request()（复用现有重试/代理）
    3. 调用 kb_update._parse_arxiv_entries() 解析 XML
    4. 去重：扫描 output/parsed/*.json 的 arxiv_id
    5. 对去重后的论文调用 kb_update.arxiv_download() 下载 TeX
    6. 调用 kb_update.batch_ingest() 全流程入库
    7. 更新 interests 的 search_count 和 last_searched
    8. 生成本次同步报告 → output/digests/sync-YYYY-MM-DD.md

    每次 arXiv 请求间隔 3s（与 kb_update.py L194 保持一致）。

    返回: {"category": "...", "downloaded": N, "ingested": N, "errors": [...]}
    """

def sync_all_directions(max_results: int = 10) -> dict:
    """对所有活跃研究方向执行 sync_direction。

    遍历 interests 中所有 category，逐个调用 sync_direction()。

    返回: {"total_categories": N, "total_papers": N, "results": [...]}
    """
```

**同步报告格式** (`output/digests/sync-2026-06-22.md`)：
```markdown
# Research Sync — 2026-06-22

## ✅ LLM Efficiency (3 papers synced)
- Efficient MoE Inference (2026) — arXiv:2606.12345 → 01ABC...
- Adaptive Sparse Attention (2026) — arXiv:2606.12678 → 01DEF...
- Sparse Transformer Survey (2026) — arXiv:2606.13000 → 01GHI...

## ✅ 3D Vision (2 papers synced)
- Gaussian Splatting for Dynamic Scenes (2026) — arXiv:2606.14000 → 01JKL...
- Neural Radiance Field Acceleration (2026) — arXiv:2606.14500 → 01MNO...

---
Total: 5 new papers synced | 2 directions | Deduped: 3 existing
```

**关键依赖**: 复用 `scholar/kb_update.py` 的 `arxiv_download()` (L87-196)、`batch_ingest()` (L199-412)、`_parse_arxiv_entries()` (L37-84)；复用 `scholar/config.py` 的 `arxiv_request()` (L69-115)。**注意**：`_parse_arxiv_entries()` (L37) 是模块私有函数，通过 `from .kb_update import _parse_arxiv_entries` 导入并加注释说明依赖关系。

---

## Task 2: 修改 `scholar/config.py` — 添加路径常量 [MODIFY +6 行]

在 L35（`PDFS_DIR` 之后）添加（包含 Task 0 Hook 所需的 `LOGS_DIR`）：
```python
DIGESTS_DIR = OUTPUT_DIR / "digests"
LOGS_DIR = OUTPUT_DIR / "logs"
INTERESTS_FILE = OUTPUT_DIR / "research-interests.json"
```

在 L38 的目录创建循环中添加 `DIGESTS_DIR` 和 `LOGS_DIR`：
```python
for d in [PARSED_DIR, NOTES_DIR, DRAFTS_DIR, BIB_DIR, EXPERIMENTS_DIR, DATASETS_DIR, PDFS_DIR, DIGESTS_DIR, LOGS_DIR]:
```

---

## Task 3: 修改 `scholar/cli.py` — 注册 2 个新 CLI 命令 [MODIFY +100 行]

在文件末尾 `def main()` 之前（L2287 附近）添加 2 个命令，遵循现有 Typer `@app.command()` + Rich 输出模式（参照 L1696-1721 的 `kb-update` 命令风格）：

### 3.1 `interests` 命令（含子命令 `logs` 和 `mark-analyzed`）
```python
@app.command()
def interests(
    action: str = typer.Argument("list", help="Action: list, add, remove, logs, mark-analyzed"),
    keywords: str = typer.Option("", "--keywords", help="Comma-separated keywords (for add)"),
    category: str = typer.Option("general", "--category", help="Interest category"),
    max_results: int = typer.Option(10, "--max", help="Max results per search (for add)"),
    week: str = typer.Option("", "--week", help="Week ID like 2026-W24 (for mark-analyzed)"),
    interests_found: int = typer.Option(0, "--found", help="Number of interests found (for mark-analyzed)"),
):
    """管理研究方向 + 对话日志分析进度。"""
    # list/add/remove: 委托给 research_loop 兴趣管理函数
    # logs: 委托给 research_loop.get_unanalyzed_logs()，展示未分析的周日志
    # mark-analyzed: 委托给 research_loop.mark_week_analyzed()
```

### 3.2 `research-sync` 命令（方向确认后一条龙执行）
```python
@app.command(name="research-sync")
def research_sync(
    category: str = typer.Option("", "--category", help="Sync specific direction (empty = all)"),
    max_results: int = typer.Option(10, "--max", help="Max papers per direction"),
):
    """根据研究方向搜索 arXiv 并全流程入库。"""
    # 委托给 research_loop.sync_direction() 或 sync_all_directions()
    # 用 Rich Panel 展示同步结果
```

---

## Task 4: 修改 `scholar_mcp/server.py` — 注册 2 个 MCP 工具 [MODIFY +35 行]

在 `# ─── KB Update ───` 区域之后（L424 之后）添加，遵循 `_run_scholar()` 模式：

```python
# ─── Research Loop ──────────────────────────────────────────────

@mcp.tool()
def scholar_interests(action: str = "list", keywords: str = "", category: str = "general", week: str = "", interests_found: int = 0) -> str:
    """Manage research directions and analyze conversation logs.
    
    Actions: list, add, remove, logs (get unanalyzed week log), mark-analyzed
    """

@mcp.tool()
def scholar_research_sync(category: str = "", max_results: int = 10) -> str:
    """Search arXiv for a research direction and run full ingest pipeline.
    
    Args:
        category: Specific direction to sync (empty = all directions)
        max_results: Max papers per direction
    """
```

---

## Task 5: 创建 Skill [NEW FILE] + Command [NEW FILE] + Rule [NEW FILE] + 路由更新 [MODIFY]

### 5.1 新建 `.qoder/skills/adaptive-research/SKILL.md`

定义完整的 4 步工作流：
1. 兴趣画像查看/管理（interests list/add/remove）
2. 方向级同步（research-sync）— 搜索+下载+全流程入库
3. 结果确认（stats）
4. 定时任务配置指南

### 5.2 新建 `.qoder/commands/sync.md`

快捷命令 `/sync`，执行 research-sync + 展示结果。

### 5.3 新建 `.qoder/rules/interest-capture.md`（model_decision rule）[NEW FILE]

**这是定时任务的执行指南。** 当定时任务触发时，Agent 加载此 rule 执行日志分析：

```markdown
# 研究同步规则

当被要求执行「研究同步」或「分析对话日志」时：

1. 运行 `python -m scholar interests logs` 获取未分析的对话日志
2. 阅读日志，识别研究方向信号：
   - 讨论某个研究方向或方法（如 "MoE 推理优化"）
   - 表达某个研究想法（如 "能不能把 retrieval 和 MoE 结合"）
   - 执行了学术类 skill（如 research-survey "sparse attention"）
   - 讨论了某篇论文的核心方法
3. 忽略非学术内容（修 bug、改配置）
4. 运行 `python -m scholar interests add` 写入新方向
5. 运行 `python -m scholar interests mark-analyzed` 标记完成
6. 将方向列表发送到飞书，让用户确认要追踪哪些方向
7. 用户回复后，对每个确认的方向运行 `python -m scholar research-sync --category "方向名"`
8. 输出同步报告
```

### 5.4 修改 `.qoder/rules/pipelines.md`

路由表添加第 7 行：
```
| 7 | 研究循环 | 研究循环, 论文追踪, research loop, 新论文 | `adaptive-research` |
```

### 5.5 修改 `.qoder/rules/tools.md`

添加 Research Loop 命令参考区块。

### 5.6 修改 `.qoder/rules/identity.md`

项目结构速查中添加 `output/digests/`、`output/logs/` 和 `output/research-interests.json`。

---

## Task 6: QoderWork 定时任务配置（用户操作，零代码）

通过 Qoder Work 的「定时任务」UI 创建**一个任务**。界面字段：任务名称、计划时间（频率+时刻）、QoderWork 指令、工作目录。

### 6.1 定时任务：兴趣提取 + 方向推送 + 确认后执行（每周一次）

| UI 字段 | 填写内容 |
|---------|--------|
| 任务名称 | `Scholar Studio 研究同步` |
| 计划时间 | 每周日 09:00 |
| 工作目录 | 选择 Scholar Studio 项目根目录 |
| QoderWork 指令 | 见下方 |

```
执行研究同步任务：
1. 运行 python -m scholar interests logs 获取未分析的对话日志
2. 阅读日志，提取其中的研究方向信号（忽略纯技术操作）
3. 运行 python -m scholar interests list 查看已有方向，去重后写入新方向
4. 运行 python -m scholar interests mark-analyzed 标记该周完成
5. 将当前所有研究方向列表发送到飞书，让用户确认要追踪哪些方向
6. 用户回复后，对确认的每个方向运行 python -m scholar research-sync --category "方向名"
7. 输出同步报告
```

### 6.2 用户确认流程（IM → Qoder Work）

Agent 推送给飞书的内容：
```
📌 本周从对话中提取的研究方向：
1. MoE 推理优化
2. Sparse Attention
3. Retrieval-Augmented Generation
4. 3D Gaussian Splatting

回复编号确认要追踪的方向（如 "1,3"）
```

用户回复：
> 「1,3」

Agent 立即执行：
```bash
python -m scholar research-sync --category "MoE 推理优化"
python -m scholar research-sync --category "Retrieval-Augmented Generation"
```

**每个方向自动完成**：搜索 arXiv → 下载前 N 篇 → TeX 解析 → 图谱更新 → RAG 索引 → 阅读笔记 → 质量评分 → 分类打标签。一条龙，无需二次确认。

### 6.3 退化方案

- 电脑休眠时任务不执行 → 日志持续积累不丢失，唤醒后下次触发时自动补偿
- IM 未配置 → 方向列表保存到 `output/digests/` 文件，用户手动执行 `/sync` 查看
- 兴趣画像为空 → `research-sync` 提示「请先添加研究方向」，不崩溃

---

## 依赖关系

```
Task 2 (config.py) ──→ Task 0 (Hook 日志采集)
Task 2 (config.py) ──→ Task 1 (research_loop.py)
Task 0 (Hook) ──→ Task 6 (定时任务)
Task 1 ──→ Task 3 (CLI 命令)
Task 1 ──→ Task 4 (MCP 工具)
Task 3 ──→ Task 5 (Skill/Command/Rule)
Task 5 ──→ Task 6 (QoderWork)
```

**推荐执行顺序**: Task 2 (config.py) → Task 0 (Hook) → Task 1 (research_loop.py) → Task 3 (CLI) → Task 4 (MCP) → Task 5 (Skill/Rule) → 验证 → Task 6 (QoderWork)

---

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| arXiv API 限流（多关键词连续请求） | 每次请求间隔 3s，复用 `config.arxiv_request()` 的 3 次重试 |
| 方向关键词搜索不精准 | 复用 `kb_update.arxiv_download()` 的成熟搜索逻辑，支持逗号分隔多关键词 |
| 兴趣文件不存在时命令崩溃 | `load_interests()` 返回空模板 + 友好提示「请先添加研究兴趣」 |
| `cli.py` 继续膨胀 | 新命令仅做参数解析 + Rich 输出，所有逻辑委托给 `research_loop.py` |
| QoderWork 定时任务不执行（电脑休眠） | 日志持续积累不丢失，唤醒后下次触发时自动补偿 |
| Hook 日志文件过大 | 按周轮转（`week-YYYY-WNN.jsonl`），一个文件 = 一个分析周期，完成后标记归档 |
| 兴趣提取质量不稳定 | Rule 提供明确的提取指南 + 忽略列表（非学术内容）；画像支持手动修正 |
| PowerShell Hook 编码问题 | 使用 UTF-8 BOM 编码（项目已有此规范） |
| Stop Hook stdin JSON 结构未知 | 实施前先手动触发一次 Stop Hook，打印 stdin 到文件查看实际 JSON 结构，确认 user_messages 字段是否存在 |

---

## 被否决的方案

| 方案 | 否决原因 |
|------|--------|
| ~~Hook 直接做兴趣提取（Stop 事件触发正则/NLP）~~ | **已演进为两阶段设计**：Hook 只做无脑日志记录，语义分析交给定时任务中的 Agent |
| 用 `arxiv_download(query=arxiv_id)` 做选择性入库 | `all:` 搜索不可靠，改用 `download_by_arxiv_id()` + arXiv API `id_list` 参数精确获取 |
| 两个定时任务分开（兴趣提取 + 论文推荐） | 用户确认的是方向而非论文，合并为一个任务：提取→推送→确认→一条龙执行 |
| Rule 单独承担兴趣捕获 | Rule 是软约束，Agent 可能遗忘执行；不可靠 |
| 用户主动声明兴趣 | 用户不会主动管理兴趣画像，不现实 |
| Agent 对话结束时询问「要追踪吗」 | 用户 rarely 说「今天就到这里」，打断工作流 |
| arXiv 搜索缓存层 | MVP 阶段过早优化；兴趣关键词通常 < 10 个，搜索频率为每周 1-2 次 |
| ThreadPoolExecutor 并行搜索 | arXiv 要求 ≥3s 间隔，并行反而增加限流风险 |
| SearchProvider 抽象接口 | 当前只有 arXiv 一个数据源，等有集成需求时再添加 |
| Windows Task Scheduler 自建调度 | QoderWork 原生支持 Scheduled Tasks，自建增加维护成本 |
| Python IM SDK 集成 | IM 推送完全由 QoderWork 平台处理 |

---

## 变更文件清单

| 文件 | 类型 | 预估行数 |
|------|------|--------|
| `.qoder/hooks/log-conversation.ps1` | NEW | ~30 行 |
| `.qoder/hooks/hooks.json` | MODIFY | +5 行 |
| `scholar/config.py` | MODIFY | +6 行 |
| `scholar/research_loop.py` | NEW | ~280 行（含 `sync_direction`） |
| `scholar/cli.py` | MODIFY | +100 行（末尾追加） |
| `scholar_mcp/server.py` | MODIFY | +35 行（L424 后插入） |
| `.qoder/skills/adaptive-research/SKILL.md` | NEW | ~80 行 |
| `.qoder/commands/sync.md` | NEW | ~20 行 |
| `.qoder/rules/interest-capture.md` | NEW | ~40 行 |
| `.qoder/rules/pipelines.md` | MODIFY | +1 行 |
| `.qoder/rules/tools.md` | MODIFY | +10 行 |
| `.qoder/rules/identity.md` | MODIFY | +3 行 |