## 1. 系统概述
本项目（Scholar Studio）未采用传统的文件日志框架（如 `logging` 模块或 Loguru），而是构建了一套**基于 Rich Console 的交互式 CLI 输出系统**。其核心设计理念是将所有运行时信息、状态反馈和错误提示直接渲染到终端，通过丰富的样式（颜色、面板、表格、进度条）提供高可读性的实时反馈。

此外，项目通过 **Hooks 机制**（`.qoder/hooks/log-conversation.ps1`）实现了**对话日志的自动采集**，将用户与 Agent 的交互内容持久化为 JSONL 文件，用于后续的“自适应研究闭环”（Adaptive Research Loop）分析。

## 2. 核心组件与实现

### 2.1 共享 Console 实例
- **位置**: `scholar/_shared.py`
- **实现**: 创建全局单例 `console = Console()`，并在所有命令模块中共享。
- **作用**: 统一输出通道，确保样式一致性和线程安全（Rich Console 默认线程安全）。

```python
from rich.console import Console
console = Console()
```

### 2.2 结构化输出模式
项目广泛使用 Rich 的高级组件来结构化输出信息，而非简单的文本打印：
- **Panel (面板)**: 用于包裹关键结果块，如论文解析详情、知识库统计、批量处理总结。
  - *示例*: `console.print(Panel(f"Title: {title}\nAuthors: {authors}", title="Parsed OK"))`
- **Table (表格)**: 用于展示列表数据，如论文扫描状态、搜索结果、领域分布。
  - *示例*: `table.add_row(status, ulid, "[green]Y[/]", "[red]N[/]")`
- **Progress (进度条)**: 用于长时间运行的批量任务（如 `parse-all`, `bootstrap`）。
  - *示例*: `with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress: ...`
- **颜色标记**: 使用 `[green]OK[/]`, `[red]Error[/]`, `[yellow]Warning[/]`, `[cyan]Info[/]` 等内联样式区分信息等级。

### 2.3 对话日志采集 (Hook)
- **位置**: `.qoder/hooks/log-conversation.ps1`
- **触发时机**: Qoder Agent 会话结束（Stop 事件）。
- **逻辑**:
  1. 读取当前会话的 Transcript（转录记录）。
  2. 提取用户查询（User Query）和助手回复（Assistant Response）。
  3. 按周轮转写入 `output/logs/week-YYYY-WNN.jsonl`。
  4. 支持重试机制（3×800ms）以确保在 IDE 关闭前完成写入。
- **用途**: 这些日志被 `scholar/research_loop.py` 中的 `get_unanalyzed_logs()` 读取，用于提取用户的研究兴趣并触发自动论文同步。

## 3. 日志级别与约定

虽然没有显式的 `DEBUG/INFO/WARN` 枚举，但通过颜色和样式隐式定义了信息等级：

| 等级 | 样式约定 | 使用场景 |
|------|----------|----------|
| **Success** | `[green]...[/]` | 操作成功完成（如 "Parsed OK", "Ingested"） |
| **Error** | `[red]...[/]` | 致命错误或异常中断（如 "Parse failed", "DB connection error"） |
| **Warning** | `[yellow]...[/]` | 非致命问题或降级处理（如 "Neo4j unavailable", "Fallback to keyword search"） |
| **Info** | `[cyan]...[/]` 或默认 | 常规流程提示（如 "Parsing...", "Initializing..."） |
| **Detail** | `[dim]...[/]` | 次要信息或元数据（如路径、模式标识） |

## 4. 开发者规范

1. **禁止使用 `print()`**: 所有输出必须通过 `console.print()` 进行，以确保样式统一和在非 TTY 环境下的兼容性。
2. **使用共享实例**: 始终从 `scholar._shared` 导入 `console`，不要自行创建新的 `Console()` 实例。
3. **结构化优先**: 
   - 列表数据使用 `Table`。
   - 关键结果块使用 `Panel`。
   - 长时任务使用 `Progress`。
4. **错误处理**: 捕获异常后，使用 `[red]` 标记错误信息，并视情况使用 `typer.Exit(1)` 终止程序。
5. **静默失败与降级**: 对于非核心依赖（如 Neo4j、Embedding API），连接失败时应输出 `[yellow]` 警告并降级功能，而不是崩溃。
6. **日志持久化**: 若需持久化运行日志，应依赖 Hook 机制或手动写入 `output/logs/`，而非配置 logging 文件处理器。

## 5. 关键文件索引

- `scholar/_shared.py`: Console 实例定义。
- `scholar/cli.py`: CLI 入口，组装命令。
- `scholar/commands/*.py`: 具体命令实现，包含所有 `console.print` 调用。
- `scholar/research_loop.py`: 对话日志的读取与分析逻辑。
- `.qoder/hooks/log-conversation.ps1`: 对话日志的自动采集脚本。
- `output/logs/`: 持久化对话日志存储目录。