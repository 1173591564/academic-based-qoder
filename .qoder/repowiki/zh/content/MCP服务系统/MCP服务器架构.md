# MCP服务器架构

<cite>
**本文引用的文件**
- [server.py](file://scholar_mcp/server.py)
- [__main__.py](file://scholar_mcp/__main__.py)
- [_state.py](file://scholar/_state.py)
- [_shared.py](file://scholar/_shared.py)
- [db.py](file://scholar/db.py)
- [id_resolver.py](file://scholar/id_resolver.py)
- [cli.py](file://scholar/cli.py)
- [config.py](file://scholar/config.py)
- [year_fix.py](file://scholar/year_fix.py)
- [mcp.json](file://plugin/mcp.json)
- [requirements.txt](file://requirements.txt)
- [__main__.py](file://scholar/__main__.py)
</cite>

## 更新摘要
**变更内容**
- 异常处理增强：year_fix工具改进（增加跳过计数反馈）
- try/finally结构改进：graph_query和citation_network工具的资源管理
- atexit处理程序：确保数据库连接池正确关闭
- 统一的错误处理策略：所有工具函数现在使用try/except结构

## 目录
1. [引言](#引言)
2. [项目结构](#项目结构)
3. [核心组件](#核心组件)
4. [架构总览](#架构总览)
5. [详细组件分析](#详细组件分析)
6. [依赖分析](#依赖分析)
7. [性能考虑](#性能考虑)
8. [故障排查指南](#故障排查指南)
9. [结论](#结论)
10. [附录](#附录)

## 引言
本文件面向MCP服务器架构，系统性阐述基于FastMCP框架的Scholar Studio MCP服务器设计与实现。重点包括：
- FastMCP框架的使用与服务器初始化配置
- 工具注册机制与生命周期管理
- 将scholar CLI命令封装为MCP工具的实现模式
- **新增**：异常处理增强与资源管理改进
- **新增**：atexit处理程序确保数据库连接池正确关闭
- 进程间通信机制、超时管理与错误处理策略
- 服务器启动流程、配置选项、日志记录与监控指标
- 并发处理、资源管理与性能优化技巧

## 项目结构
该项目采用"多模块分层"组织方式，MCP服务器位于独立包中，通过**直接方法调用**而非子进程调用现有CLI能力，形成"MCP适配层 + 核心业务模块"的高效架构。

```mermaid
graph TB
subgraph "MCP服务器层"
A["scholar_mcp/server.py<br/>FastMCP实例与工具注册<br/>异常处理增强"]
B["scholar_mcp/__main__.py<br/>入口点<br/>atexit处理程序"]
end
subgraph "核心业务层"
C["scholar/_state.py<br/>共享状态管理<br/>连接池+缓存+清理"]
D["scholar/db.py<br/>数据库抽象层<br/>连接池支持"]
E["scholar/id_resolver.py<br/>ID解析器<br/>内存缓存"]
F["scholar/_shared.py<br/>共享对象<br/>CLI与MCP共享"]
G["scholar/year_fix.py<br/>年份补全工具<br/>增强的统计反馈"]
end
subgraph "IDE集成"
H["plugin/mcp.json<br/>MCP服务器配置"]
end
subgraph "依赖"
I["requirements.txt<br/>mcp>=1.0等依赖"]
J["scholar/cli.py<br/>CLI入口点"]
end
A --> C
B --> A
C --> D
C --> E
F --> J
G --> A
H --> A
I --> A
I --> J
```

**图表来源**
- [server.py:1-945](file://scholar_mcp/server.py#L1-L945)
- [__main__.py:1-13](file://scholar_mcp/__main__.py#L1-L13)
- [_state.py:1-131](file://scholar/_state.py#L1-L131)
- [db.py:1-308](file://scholar/db.py#L1-L308)
- [id_resolver.py:1-107](file://scholar/id_resolver.py#L1-L107)
- [year_fix.py:1-420](file://scholar/year_fix.py#L1-L420)
- [mcp.json:1-16](file://plugin/mcp.json#L1-L16)
- [requirements.txt:1-14](file://requirements.txt#L1-L14)

**章节来源**
- [server.py:1-945](file://scholar_mcp/server.py#L1-L945)
- [__main__.py:1-13](file://scholar_mcp/__main__.py#L1-L13)
- [_state.py:1-131](file://scholar/_state.py#L1-L131)
- [db.py:1-308](file://scholar/db.py#L1-L308)
- [id_resolver.py:1-107](file://scholar/id_resolver.py#L1-L107)
- [year_fix.py:1-420](file://scholar/year_fix.py#L1-L420)
- [mcp.json:1-16](file://plugin/mcp.json#L1-L16)
- [requirements.txt:1-14](file://requirements.txt#L1-L14)

## 核心组件
- FastMCP实例与工具注册
  - 使用FastMCP创建服务器实例，并在其中注册大量工具函数，每个工具对应一个scholar CLI命令或文件读取操作。
  - 工具函数统一通过装饰器注册到FastMCP实例上，形成标准化的MCP工具集合。
- **新增**：异常处理增强
  - 所有工具函数现在使用统一的try/except结构，提供更可靠的错误处理。
  - year_fix工具增加了详细的统计反馈，包括跳过计数。
  - graph_query和citation_network工具使用try/finally确保资源正确释放。
- **新增**：atexit处理程序
  - 在入口点注册atexit处理程序，确保数据库连接池在服务器退出时正确关闭。
  - 通过lambda函数优雅地调用共享状态的close()方法。
- **新增**：直接方法调用与共享状态管理
  - 所有工具内部直接调用核心业务模块，而非通过subprocess执行CLI命令。
  - 通过`init_shared_state()`初始化共享状态，包括连接池、ID解析器缓存和文件缓存。
- **新增**：连接池支持
  - PostgreSQL连接池（ThreadedConnectionPool）支持多线程并发访问。
  - 每个工具通过共享状态获取数据库实例，避免重复连接开销。
- 配置与环境变量
  - 通过config.py集中管理路径、数据库连接、Neo4j、RAG嵌入等配置项；同时加载.env文件中的敏感配置。
- IDE集成配置
  - plugin/mcp.json声明了MCP服务器的启动命令、参数与环境变量，供IDE（如Qoder）直接调用。

**章节来源**
- [server.py:17-25](file://scholar_mcp/server.py#L17-L25)
- [server.py:41-945](file://scholar_mcp/server.py#L41-L945)
- [__main__.py:1-13](file://scholar_mcp/__main__.py#L1-L13)
- [_state.py:20-131](file://scholar/_state.py#L20-L131)
- [db.py:24-106](file://scholar/db.py#L24-L106)
- [mcp.json:1-16](file://plugin/mcp.json#L1-L16)

## 架构总览
下图展示了从IDE到MCP服务器、再到核心业务模块的完整调用链路与数据流，体现了直接方法调用的优势和异常处理改进。

```mermaid
sequenceDiagram
participant IDE as "IDE/Qoder"
participant MCP as "MCP服务器<br/>FastMCP实例"
participant State as "共享状态<br/>连接池+缓存+清理"
participant Core as "核心业务模块<br/>直接方法调用"
IDE->>MCP : "MCP请求工具名+参数"
MCP->>State : "获取共享状态"
State->>Core : "直接调用业务方法"
Core-->>State : "返回业务结果"
State-->>MCP : "返回处理结果"
MCP-->>IDE : "返回工具结果字符串"
Note over MCP : "异常处理：try/except<br/>资源管理：try/finally"
Note over State : "atexit清理：<br/>连接池关闭"
```

**图表来源**
- [server.py:17-25](file://scholar_mcp/server.py#L17-L25)
- [_state.py:120-131](file://scholar/_state.py#L120-L131)
- [__main__.py:9-10](file://scholar_mcp/__main__.py#L9-L10)

**章节来源**
- [server.py:17-25](file://scholar_mcp/server.py#L17-L25)
- [_state.py:120-131](file://scholar/_state.py#L120-L131)
- [__main__.py:9-10](file://scholar_mcp/__main__.py#L9-L10)

## 详细组件分析

### FastMCP服务器初始化与生命周期
- 初始化
  - 创建FastMCP实例，传入服务器名称与指令描述，作为IDE侧的元信息展示。
  - **新增**：在入口点调用`init_shared_state()`进行一次性初始化。
  - **新增**：注册atexit处理程序，确保服务器退出时资源正确清理。
- 生命周期
  - 提供main()入口，直接调用mcp.run()启动服务器，交由FastMCP框架管理事件循环与请求分发。
- 入口点
  - scholar_mcp/__main__.py将执行委托给server.main()，并在启动时初始化共享状态。
  - **新增**：注册atexit处理程序，调用`get_state().close()`确保连接池关闭。

```mermaid
flowchart TD
Start(["启动"]) --> InitState["init_shared_state() 初始化共享状态"]
InitState --> RegisterCleanup["注册atexit处理程序"]
RegisterCleanup --> NewMCP["创建FastMCP实例"]
NewMCP --> RegisterTools["注册工具函数<br/>统一异常处理"]
RegisterTools --> Run["mcp.run() 启动服务"]
Run --> Serve["接收MCP请求并路由到工具"]
Serve --> Cleanup["服务器退出时清理资源"]
Cleanup --> End(["退出由框架控制"])
```

**图表来源**
- [__main__.py:1-13](file://scholar_mcp/__main__.py#L1-L13)
- [server.py:939-945](file://scholar_mcp/server.py#L939-L945)

**章节来源**
- [__main__.py:1-13](file://scholar_mcp/__main__.py#L1-L13)
- [server.py:939-945](file://scholar_mcp/server.py#L939-L945)

### **新增**：异常处理增强与资源管理
- 统一异常处理模式
  - 所有工具函数现在使用统一的try/except结构，提供一致的错误处理体验。
  - 异常被捕获后返回友好的错误消息，而不是让异常传播到IDE侧。
- year_fix工具改进
  - 增加了详细的统计反馈，包括跳过计数（skipped）。
  - 提供更全面的状态报告，帮助用户了解工具执行效果。
- try/finally结构改进
  - graph_query和citation_network工具使用try/finally确保GraphDB连接正确关闭。
  - 即使发生异常，也能保证数据库连接被正确释放。
- atexit处理程序
  - 注册lambda函数`lambda: get_state() and get_state().close()`确保连接池关闭。
  - 在服务器进程结束时自动清理所有数据库连接。

```mermaid
flowchart TD
ToolCall["工具调用"] --> TryBlock["try块<br/>执行业务逻辑"]
TryBlock --> Success{"执行成功？"}
Success --> |是| Return["返回结果"]
Success --> |否| CatchBlock["except块<br/>捕获异常"]
CatchBlock --> ErrorMsg["返回错误消息"]
Return --> FinallyBlock["finally块<br/>清理资源"]
ErrorMsg --> FinallyBlock
FinallyBlock --> CloseDB["关闭数据库连接"]
CloseDB --> End["结束"]
```

**图表来源**
- [server.py:276-291](file://scholar_mcp/server.py#L276-L291)
- [server.py:310-330](file://scholar_mcp/server.py#L310-L330)
- [server.py:339-371](file://scholar_mcp/server.py#L339-L371)

**章节来源**
- [server.py:276-291](file://scholar_mcp/server.py#L276-L291)
- [server.py:310-330](file://scholar_mcp/server.py#L310-L330)
- [server.py:339-371](file://scholar_mcp/server.py#L339-L371)
- [__main__.py:9-10](file://scholar_mcp/__main__.py#L9-L10)

### **新增**：共享状态管理与连接池
- 共享状态设计
  - `SharedState`类提供进程级共享状态，包含PostgreSQL连接池、ID解析器缓存和LRU缓存。
  - 通过`init_shared_state()`在启动时初始化，避免后续每次调用的重复开销。
- 连接池支持
  - 使用psycopg2的ThreadedConnectionPool，配置minconn=2, maxconn=8。
  - 支持多线程并发访问，自动管理连接生命周期。
  - **新增**：提供close()方法用于优雅关闭所有连接。
- 缓存策略
  - ID解析器缓存：预加载555个JSON文件，首次调用约280ms。
  - 解析JSON缓存：LRU缓存最近访问的论文数据，最大100项。
- 线程安全
  - 使用threading.Lock保护共享资源的并发访问。
  - 提供get_db()方法返回带有连接池的Database实例。

```mermaid
flowchart TD
Init["init_shared_state()"] --> Pool["初始化连接池<br/>ThreadedConnectionPool"]
Init --> Resolver["预加载ID解析器<br/>缓存555个JSON文件"]
Init --> Cache["初始化LRU缓存<br/>最大100项"]
Pool --> DB["Database实例<br/>支持连接池"]
Resolver --> ID["ID解析器缓存"]
Cache --> Parsed["解析JSON缓存"]
Pool --> Close["close()方法<br/>优雅关闭连接"]
```

**图表来源**
- [_state.py:90-104](file://scholar/_state.py#L90-L104)
- [_state.py:47-61](file://scholar/_state.py#L47-L61)
- [_state.py:65-87](file://scholar/_state.py#L65-L87)
- [_state.py:105-113](file://scholar/_state.py#L105-L113)

**章节来源**
- [_state.py:20-131](file://scholar/_state.py#L20-L131)
- [db.py:24-106](file://scholar/db.py#L24-L106)

### 工具注册机制与实现模式
- 装饰器注册
  - 所有工具函数通过@mcp.tool()进行注册，统一暴露为MCP工具。
- **更新**：直接方法调用实现模式
  - 工具函数直接调用核心业务模块，不再通过subprocess执行CLI命令。
  - 通过`get_state()`获取共享状态，实现高效的数据库访问和缓存。
  - 大多数工具仅做参数验证与结果处理，核心逻辑在核心业务模块中实现。
- **新增**：统一异常处理
  - 所有工具函数现在使用try/except结构，提供一致的错误处理体验。
  - year_fix工具增加了详细的统计反馈，包括跳过计数。
- 文件读取型工具
  - 对于需要直接读取文件的工具（如读取自动生成的笔记、质量评分、解析后的JSON），在工具内解析ID并定位文件路径，若不存在则返回提示信息。

```mermaid
flowchart TD
ToolCall["工具调用"] --> GetState["get_state() 获取共享状态"]
GetState --> DirectCall["直接调用核心业务方法"]
DirectCall --> CacheCheck{"检查缓存"}
CacheCheck --> |命中| Return["返回缓存结果"]
CacheCheck --> |未命中| DBAccess["访问数据库/文件"]
DBAccess --> Process["处理业务逻辑"]
Process --> CacheUpdate["更新缓存"]
CacheUpdate --> Return
```

**图表来源**
- [server.py:28-35](file://scholar_mcp/server.py#L28-L35)
- [_state.py:37-43](file://scholar/_state.py#L37-L43)

**章节来源**
- [server.py:41-945](file://scholar_mcp/server.py#L41-L945)
- [server.py:28-35](file://scholar_mcp/server.py#L28-L35)

### **移除**：进程间通信机制与超时管理
- **更新**：直接方法调用优势
  - 消除了subprocess调用的进程开销，实现近140倍性能提升。
  - 直接调用核心业务方法，无需等待进程启动和I/O传输。
  - 通过共享状态管理实现资源复用，避免重复初始化。
- **更新**：简化错误处理
  - 直接调用核心业务方法时，异常会自动传播到MCP框架。
  - 通过try-catch块捕获业务逻辑异常，提供友好的错误信息。
  - **新增**：统一的异常处理模式，所有工具函数都有相同的错误处理策略。

**章节来源**
- [server.py:37-50](file://scholar_mcp/server.py#L37-L50)

### 错误处理策略
- **更新**：统一异常处理模式
  - 所有工具函数现在使用统一的try/except结构，提供一致的错误处理体验。
  - year_fix工具增加了详细的统计反馈，包括跳过计数（skipped）。
  - graph_query和citation_network工具使用try/finally确保资源正确释放。
- 文件访问类工具
  - 当目标文件不存在时，返回明确提示，指导用户先执行相应CLI命令生成产物。
- CLI层错误
  - 核心CLI命令本身也具备丰富的错误提示与退出码，MCP层复用其输出。

**章节来源**
- [server.py:276-291](file://scholar_mcp/server.py#L276-L291)
- [server.py:310-330](file://scholar_mcp/server.py#L310-L330)
- [server.py:339-371](file://scholar_mcp/server.py#L339-L371)

### 服务器启动流程与IDE集成
- 启动流程
  - IDE通过plugin/mcp.json中的命令与参数启动MCP服务器。
  - 服务器入口scholar_mcp/__main__.py调用`init_shared_state()`初始化共享状态，然后调用server.main()。
  - `init_shared_state()`执行一次性初始化，包括连接池和缓存预加载。
  - **新增**：注册atexit处理程序，确保服务器退出时资源正确清理。
- 集成配置
  - mcp.json定义了服务器命令、参数以及必要的环境变量（如数据库与图数据库地址），确保服务器运行时具备所需依赖。

```mermaid
sequenceDiagram
participant IDE as "IDE"
participant MCPJSON as "plugin/mcp.json"
participant Py as "python -m scholar_mcp"
participant Init as "init_shared_state()"
participant Cleanup as "atexit.register()"
participant Srv as "server.main()"
participant M as "FastMCP.run()"
IDE->>MCPJSON : "读取服务器配置"
IDE->>Py : "按配置启动进程"
Py->>Init : "初始化共享状态"
Init->>Init : "连接池+缓存预加载"
Py->>Cleanup : "注册清理处理程序"
Cleanup->>Cleanup : "lambda : get_state().close()"
Py->>Srv : "调用入口函数"
Srv->>M : "启动MCP服务"
M-->>IDE : "提供工具列表与调用接口"
Note over Py : "服务器退出时<br/>自动清理资源"
```

**图表来源**
- [mcp.json:1-16](file://plugin/mcp.json#L1-L16)
- [__main__.py:1-13](file://scholar_mcp/__main__.py#L1-L13)

**章节来源**
- [mcp.json:1-16](file://plugin/mcp.json#L1-L16)
- [__main__.py:1-13](file://scholar_mcp/__main__.py#L1-L13)

### 配置选项与环境变量
- 项目根与输出目录
  - 通过config.py统一管理数据与输出目录，确保CLI与MCP服务器共享一致的文件布局。
- 数据库与图数据库
  - PostgreSQL与Neo4j的连接信息通过环境变量注入，便于在不同环境中灵活切换。
  - **新增**：连接池配置在共享状态中统一管理。
- RAG嵌入与LaTeX编译
  - 嵌入模型与API密钥、LaTeX引擎等通过环境变量配置，满足不同部署需求。
- CLI入口
  - scholar/__main__.py将命令转发至cli.py中的Typer应用，形成统一的命令入口。

**章节来源**
- [config.py:20-67](file://scholar/config.py#L20-L67)
- [__main__.py:1-8](file://scholar/__main__.py#L1-L8)

### 日志记录与监控指标
- 输出格式
  - 工具统一返回字符串，IDE侧负责渲染与展示；CLI层使用rich进行终端友好输出，MCP层复用其标准输出。
- 监控建议
  - 可在MCP服务器层增加请求计数、平均响应时间、超时次数等指标，结合日志记录请求ID与参数摘要，便于问题追踪与性能分析。
  - **新增**：连接池使用率监控、缓存命中率统计等指标。
  - **新增**：异常处理统计，跟踪工具执行成功率。

### 并发处理、资源管理与性能优化
- **更新**：并发与资源管理
  - 通过ThreadedConnectionPool支持多线程并发访问，避免锁竞争。
  - 共享状态在进程启动时初始化，后续调用无需重复初始化昂贵资源。
  - LRU缓存减少重复文件I/O和数据库查询。
  - **新增**：atexit处理程序确保资源正确清理。
- 资源管理
  - 连接池自动管理连接生命周期，避免连接泄漏。
  - 缓存大小限制（100项）防止内存过度占用。
  - **新增**：try/finally结构确保数据库连接正确关闭。
- 性能优化
  - **新增**：近140倍性能提升，消除进程间通信开销。
  - **新增**：缓存预加载，首次调用后所有后续调用都受益。
  - **新增**：连接池复用，避免重复建立数据库连接。
  - **新增**：统一异常处理减少异常传播开销。

## 依赖分析
- 外部依赖
  - mcp>=1.0：提供FastMCP框架能力。
  - typer、rich：CLI命令定义与终端渲染。
  - **新增**：psycopg2：PostgreSQL数据库驱动，支持连接池。
  - 数据库与图数据库驱动：PostgreSQL与Neo4j。
  - 其他：PyMuPDF、dotenv等。
- 内部耦合
  - MCP服务器与CLI通过共享状态解耦，耦合度降低，便于独立演进与测试。
  - **新增**：atexit模块用于资源清理。

```mermaid
graph LR
MCP["MCP服务器"] --> |直接调用| Core["核心业务模块"]
MCP --> |共享状态| State["共享状态管理"]
State --> |连接池| DB["数据库抽象层"]
State --> |缓存| Cache["ID解析器+文件缓存"]
MCP --> |读取| Config["config.py"]
Core --> |读取| Config
MCP --> |依赖| Req["requirements.txt"]
Core --> |依赖| Req
MCP --> |清理| Atexit["atexit模块"]
```

**图表来源**
- [server.py:12](file://scholar_mcp/server.py#L12)
- [requirements.txt:1-14](file://requirements.txt#L1-14)
- [_state.py:16-17](file://scholar/_state.py#L16-L17)
- [db.py:12](file://scholar/db.py#L12)
- [__main__.py:2](file://scholar_mcp/__main__.py#L2)

**章节来源**
- [requirements.txt:1-14](file://requirements.txt#L1-L14)
- [server.py:12](file://scholar_mcp/server.py#L12)
- [_state.py:16-17](file://scholar/_state.py#L16-L17)
- [db.py:12](file://scholar/db.py#L12)
- [__main__.py:2](file://scholar_mcp/__main__.py#L2)

## 性能考虑
- **更新**：性能优化策略
  - **近140倍性能提升**：从子进程调用转换为直接方法调用，消除进程启动和I/O传输开销。
  - **连接池优化**：ThreadedConnectionPool支持多线程并发，避免连接竞争。
  - **缓存优化**：ID解析器缓存和LRU文件缓存减少重复计算和磁盘访问。
  - **异常处理优化**：统一的异常处理模式减少异常传播开销。
- 工具粒度与超时
  - 工具通过直接方法调用，无需设置超时；对于长时间操作，工具内部可自行控制。
  - **新增**：try/finally结构确保长时间操作的资源正确清理。
- I/O与缓存
  - 对解析后的大文件与数据库查询进行缓存，减少重复计算与磁盘访问。
  - **新增**：缓存预加载，首次调用后所有后续调用都受益。
- 并发与限流
  - **新增**：连接池自动处理并发，无需手动限流。
  - **新增**：线程安全的共享状态管理。
  - **新增**：atexit处理程序确保并发环境下的资源正确清理。

## 故障排查指南
- 服务器无法启动
  - 检查mcp.json中的命令与参数是否正确，确认Python解释器可用。
  - **新增**：检查数据库连接池初始化是否成功。
  - **新增**：确认atexit处理程序已正确注册。
- 工具执行异常
  - 查看共享状态初始化是否正常，确认连接池和缓存是否可用。
  - 检查核心业务模块的异常信息，关注直接调用的错误栈。
  - **新增**：查看year_fix工具的详细统计反馈，包括跳过计数。
- 文件读取失败
  - 确认目标文件是否存在，必要时先执行对应的CLI命令生成产物。
- CLI错误信息
  - 复核CLI命令的参数与输入，关注rich输出中的错误提示与建议。
- 资源泄漏问题
  - **新增**：检查服务器退出时是否正确关闭数据库连接池。
  - **新增**：确认atexit处理程序正常工作。

**章节来源**
- [mcp.json:1-16](file://plugin/mcp.json#L1-L16)
- [_state.py:90-113](file://scholar/_state.py#L90-L113)
- [server.py:276-291](file://scholar_mcp/server.py#L276-L291)
- [__main__.py:9-10](file://scholar_mcp/__main__.py#L9-L10)

## 结论
本MCP服务器通过FastMCP框架将成熟的scholar CLI能力无缝暴露为IDE原生工具集，**通过重大架构升级实现了近140倍性能提升**。新的直接方法调用模式消除了子进程开销，结合共享状态管理、连接池支持和智能缓存策略，实现了高效、稳定的学术研究工具链。

**最新更新增强了异常处理能力和资源管理可靠性**：
- year_fix工具提供了更详细的统计反馈，包括跳过计数
- graph_query和citation_network工具使用try/finally确保资源正确释放
- atexit处理程序确保数据库连接池在服务器退出时正确关闭

配合完善的配置体系与IDE集成配置，可在多种环境下快速部署与维护。未来可在监控指标、异步任务与并发控制方面进一步增强，以支撑更大规模的研究场景。

## 附录
- 关键实现参考路径
  - FastMCP实例与工具注册：[server.py:17-25](file://scholar_mcp/server.py#L17-L25)，[server.py:41-945](file://scholar_mcp/server.py#L41-L945)
  - **新增**：异常处理增强：[server.py:276-291](file://scholar_mcp/server.py#L276-L291)，[server.py:310-330](file://scholar_mcp/server.py#L310-L330)，[server.py:339-371](file://scholar_mcp/server.py#L339-L371)
  - **新增**：atexit处理程序：[__main__.py:9-10](file://scholar_mcp/__main__.py#L9-L10)
  - **新增**：共享状态初始化：[__main__.py:4-8](file://scholar_mcp/__main__.py#L4-L8)，[_state.py:120-131](file://scholar/_state.py#L120-L131)
  - **新增**：连接池支持：[db.py:24-106](file://scholar/db.py#L24-L106)，[_state.py:90-104](file://scholar/_state.py#L90-L104)
  - 文件读取工具示例：[server.py:637-661](file://scholar_mcp/server.py#L637-L661)，[server.py:666-677](file://scholar_mcp/server.py#L666-L677)
  - CLI入口与命令定义：[__main__.py:1-8](file://scholar/__main__.py#L1-L8)，[cli.py:1-25](file://scholar/cli.py#L1-L25)
  - 配置与环境变量：[config.py:20-67](file://scholar/config.py#L20-L67)
  - IDE集成配置：[mcp.json:1-16](file://plugin/mcp.json#L1-L16)
  - 依赖声明：[requirements.txt:1-14](file://requirements.txt#L1-L14)
  - **新增**：year_fix工具：[year_fix.py:165-239](file://scholar/year_fix.py#L165-L239)