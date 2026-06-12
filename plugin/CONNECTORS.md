# Connector 依赖

Scholar Studio 的 MCP Server 和 CLI 工具依赖以下外部服务。安装插件后，请确保这些服务已启动。

## PostgreSQL

- **用途**：存储 440+ 篇论文的元数据、章节、公式、引用关系（`scholar bootstrap` 全量导入）
- **资源**：Docker 容器（镜像 `postgres:16-alpine`，端口 5433）
- **配置方式**：
  ```bash
  cd academic-based-qoder
  ./startup.ps1
  ```
  或手动启动：`docker run -d -p 5433:5432 -e POSTGRES_DB=scholar -e POSTGRES_PASSWORD=scholar postgres:16-alpine`

## Neo4j（可选）

- **用途**：引用网络分析、概念图谱查询（`graph-build`、`graph-query`、`cite-network` 命令）
- **资源**：Docker 容器（镜像 `neo4j:5-community`，端口 7474/7687）
- **配置方式**：
  ```bash
  cd academic-based-qoder
  ./startup.ps1
  ```
  如果只使用搜索和 RAG 功能，可不启动 Neo4j。

## 智谱 Embedding API（可选）

- **用途**：RAG 语义检索（`rag-index`、`rag-search` 命令）
- **资源**：智谱 AI 的 `embedding-2` 模型 API
- **配置方式**：设置环境变量 `SCHOLAR_EMBEDDING_API_KEY=你的API密钥`
  - 免费额度通常足够个人使用
  - 如果不需要语义检索，可不配置

## Scholar Python 包（必需）

- **用途**：所有 CLI 命令和 MCP Server 的后端
- **配置方式**：
  ```bash
  git clone https://gitee.com/gu-yulong1217317/academic-based-qoder.git
  cd academic-based-qoder
  pip install -r requirements.txt
  python -m scholar bootstrap
  ```
