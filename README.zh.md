# Scholar Studio

[English](README.md) | 中文

Scholar Studio 是 Python 学术研究引擎，提供 48-command CLI、16-tool MCP server、15 个本地 research skill、lexical 与 semantic retrieval、内存 citation/concept graph、论文解析、学术写作支持、实验辅助与可选 Lean4 synchronization。

## 架构

DeepSeek Harness 是独立的 client 与用户交互层。本仓库只承载 backend：`scholar/` 负责学术与 data-plane 逻辑，`scholar_mcp/` 负责 MCP adapter，`services/` 定义 deployable ownership，`infra/` 分离 Scholar 与未来 Proxy Hub 的部署资产。

第一阶段保留 authenticated DSH-to-Scholar direct path。第二阶段在本仓库新增 Proxy Hub backend 与同源 operator 管理前端，不把 tenant policy 放进 Scholar，也不把 Hub code 放进 DSH。详见[架构图](docs/architecture.md)、[最小 Proxy Hub 接口](docs/proxy-hub.md)与[管理控制台设计](docs/proxy-hub-console.md)。

## 安装

Scholar Studio 需要 Python 3.10 或更高版本。

```sh
python -m pip install .
scholar init
scholar doctor
```

`scholar init` 会在配置的 Scholar home 下安装固定本地 rule 与 15 个 skill，不覆盖用户修改的文件。Wheel 包含代码与 template，不包含论文 corpus。

## Corpus 所有权

- Remote Streamable HTTP deployment 拥有 central versioned corpus、database、embedding 与 vector index。
- Local stdio deployment 可以使用独立分发并校验的 data pack。
- Client 不从 server 同步 corpus file 或 vector index。
- Remote client 不需要 database 或 embedding-provider credential。

## MCP server

启动 local stdio transport：

```sh
python -m scholar_mcp
```

启动带 authentication 的 Streamable HTTP transport：

```sh
SCHOLAR_MCP_TRANSPORT=streamable-http \
SCHOLAR_MCP_HOST=127.0.0.1 \
SCHOLAR_MCP_PORT=8000 \
SCHOLAR_MCP_TOKEN='managed-secret' \
python -m scholar_mcp
```

Non-loopback HTTP 必须使用 Bearer token。显式 loopback no-auth 模式（`SCHOLAR_MCP_ALLOW_INSECURE_LOOPBACK=1`）仅用于本地开发或 SSH tunnel。Model-facing error 不包含 filesystem path、credential、database diagnostic 或 provider detail。

MCP server 精确发布以下 16 个工具：

1. `scholar_search`
2. `scholar_vec_search`
3. `scholar_info`
4. `scholar_section`
5. `scholar_passages`
6. `scholar_cite_network`
7. `scholar_graph_query`
8. `scholar_lineage`
9. `scholar_graph_stats`
10. `scholar_list_papers`
11. `scholar_arxiv_search`
12. `read_parsed_paper`
13. `scholar_read_output_file`
14. `read_skill`
15. `scholar_auto_notes`
16. `scholar_interests`

## DSH 集成

安装 academic preset 与 headless patch：

```sh
scholar init-dsh
```

配置 direct remote operation，且不将 literal token 写入 YAML 或 process argument：

```sh
printf '%s\n' "$SCHOLAR_REMOTE_TOKEN" \
  | scholar init-dsh \
      --remote https://scholar.example/mcp \
      --token-stdin
```

生成的 DSH composition 使用 `@deepseek-ai/dsh-mcp-client`、`@deepseek-ai/dsh-scholar-native` 与 `@deepseek-ai/dsh-skill-filesystem`。Scholar connection 与 tool synchronization 是 mandatory。Token 存入 DSH managed credential，composition 只包含其 reference。

## CLI

使用 `scholar --help` 查看权威 48-command catalog。常用操作包括：

```sh
scholar stats
scholar search "retrieval augmented generation"
scholar vec-search "How do graph retrievers improve grounding?"
scholar info <paper_id>
scholar graph-stats
scholar sync
```

Semantic search 会将 provider、database 与 index unavailable 分别报告，不与合法 zero-result response 混淆。Graph 与 vector cache 会在 authoritative corpus metadata 变化时刷新。

## 开发

```sh
python -m pip install -e '.[dev]'
docker compose -f infra/scholar/compose.yml up -d
pytest -q
python -m pip wheel . --no-deps -w dist
```

Tests 覆盖 path containment、malformed paper data、graph/index invalidation、authentication、MCP initialization、16-tool catalog、lexical 与 semantic search、DSH clean-home installation、credential storage、permission、existing-file preservation 与 rollback。

## 阶段边界

第一阶段是 direct authenticated client-to-Scholar-server product。Multi-tenant authorization、team policy、quota、centralized audit 与 corpus isolation 延期到 Proxy Hub control plane。
