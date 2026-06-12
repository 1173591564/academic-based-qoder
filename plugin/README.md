# Scholar Studio Plugin

> **本插件是"大脑"，还需要安装"身体"。** Plugin 提供 14 个 Skills + 4 个 Commands + MCP 配置，但实际执行依赖主仓库的 Python 后端和数据库。

## 架构说明

```
┌─────────────────────────────────┐
│  Scholar Studio Plugin（本插件）  │  ← Skills / Commands / Rules / Hooks
│  告诉 AI "做什么、怎么做"         │
└──────────────┬──────────────────┘
               │ 调用
┌──────────────▼──────────────────┐
│  academic-based-qoder（主仓库）   │  ← scholar CLI + MCP Server + Docker
│  真正执行搜索、解析、检索等任务    │
└─────────────────────────────────┘
```

## 安装步骤

### 第一步：安装后端（主仓库）

```bash
# 1. 克隆主仓库
git clone https://gitee.com/gu-yulong1217317/academic-based-qoder.git
cd academic-based-qoder

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 启动 PostgreSQL + Neo4j（需 Docker）
./startup.ps1

# 4. 全量初始化（解析论文、建索引、导入图谱，约 30 分钟）
python -m scholar bootstrap
```

> 以上命令中的 `scholar` 是主仓库里的 Python 包（`scholar/` 目录），不是本插件提供的。

### 第二步：安装本插件

在 QoderWork → 插件市场中搜索 **Scholar Studio** 并安装，或手动导入 `scholar-studio-2.0.0.zip`。

### 第三步：验证

安装完成后，在 QoderWork 对话中输入：
- `调研 Transformer` → 自动触发 `/research-survey`
- `知识库状态` → 自动触发 `/stats` 命令

## 包含能力

| 类型 | 数量 | 说明 |
|------|------|------|
| Skills | 14 | 8 原子 + 6 工作流 |
| Commands | 4 | stats / find / paper / health |
| Rules | 1 | Agent 角色定义 |
| Hooks | 2 | 任务完成通知 + 危险命令拦截 |
| MCP Server | 1 | Scholar MCP（41 工具） |

## Skills 列表

### 原子 Skills（8 个）
- `/paper-ingestion` — 扫描、解析并导入论文
- `/math-verification` — Lean4 数学验证
- `/paper-recommendation` — 基于引用网络的论文推荐
- `/citation-network` — 引用网络分析
- `/research-gap` — 跨论文研究空白发现
- `/review-report` — 结构化同行评审报告
- `/cold-start` — 陌生领域知识地图与学习路径
- `/experiment-code` — 根据论文生成实验代码

### 工作流（6 个）
- `/research-survey` — 全面文献调研
- `/paper-deep-dive` — 单篇深度分析（精读+质量+推导+代码）
- `/writing-pipeline` — 端到端学术写作（调研→撰写→编译→审稿）
- `/reproduce-paper` — 端到端实验复现（环境→代码→运行→对比）
- `/idea-to-paper` — 从研究点子到完整论文
- `/kb-management` — 知识库维护与自动更新
