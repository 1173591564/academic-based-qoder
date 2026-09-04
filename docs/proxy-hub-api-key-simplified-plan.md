# Proxy Hub 简化接入方案：像 LLM API 一样直接使用 Access Key

## 1. 最终目标

把普通研究用户的接入流程简化为：

```text
管理员登录 Proxy Hub
  → 创建研究用户
  → 选择租户、工具权限和配额
  → 生成一个 Access Key

用户建立 SSH 隧道
  → 把 Access Key 保存到 DSH
  → DSH 直接调用 Scholar MCP
```

用户不再需要：

- Dex 账号；
- 登录管理后台；
- Principal ID；
- Role Binding；
- 一次性兑换码；
- 先兑换 capability 再使用。

Dex/OIDC 只负责管理人员登录 Proxy Hub 控制台。

---

## 2. 推荐架构

```text
管理员
  └─ Dex/OIDC → Proxy Hub 管理控制台
                  ├─ 研究用户
                  ├─ Access Key
                  ├─ 租户与工具权限
                  ├─ 配额
                  └─ 审计与撤销

研究用户
  └─ DSH → 127.0.0.1 SSH 隧道
             → Proxy Hub /v1/mcp/scholar
                 → Scholar MCP Backend
```

SSH 隧道只负责加密传输和服务器网络准入。

Access Key 负责用户身份、租户、工具权限、配额和撤销。

Proxy Hub 继续负责：

- 验证 Access Key；
- 检查用户和租户状态；
- 检查工具 allowlist；
- 执行配额和速率限制；
- 写入审计日志；
- 选择 Scholar 后端；
- 注入 Scholar 后端 credential。

DSH 永远不直接持有 Scholar 后端 credential。

---

## 3. Access Key 形态

建议使用便于识别的格式：

```text
sk_scholar_<随机密钥>
```

例如：

```text
sk_scholar_v1_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

要求：

- 使用密码学安全随机数生成，至少 256 bit 熵；
- 完整密钥只在创建成功时显示一次；
- Proxy Hub 数据库只保存不可逆 digest，不保存明文；
- 后台列表只显示前缀和末尾四位；
- 日志、错误信息和审计记录不得包含完整密钥；
- 每个用户可以拥有多个 Key；
- 每个设备建议使用独立 Key，便于单独撤销。

---

## 4. 简化数据模型

### 4.1 研究用户

保留现有 `Principal` 表，增加：

```text
kind = oidc_operator | managed_researcher
```

`oidc_operator`：

- 由 Dex/OIDC 首次登录自动建立；
- 可以拥有控制台角色；
- 必须有 OIDC issuer 和 subject。

`managed_researcher`：

- 由管理员直接创建；
- 不需要 Dex issuer 和 subject；
- 不建立浏览器登录 session；
- 默认不能登录控制台；
- 只用于 DSH/Scholar API 身份。

研究用户字段：

```text
id
kind
display_name
email（可选）
status = active | disabled
created_by
created_at
updated_at
```

### 4.2 租户成员关系

继续使用现有 `Membership`：

```text
principal_id
tenant_id
team_id（可选）
status
```

普通研究用户只需要 Membership，不需要控制台 Role Binding。

### 4.3 Access Key

新增或由现有 `DshCapability` 演进为：

```text
id
principal_id
tenant_id
label
token_prefix
token_last_four
token_digest
allowed_tools
quota_override（可选）
rate_limit_override（可选）
expires_at（可选）
last_used_at
last_used_ip（可选）
created_by
created_at
revoked_at
revoked_by
revoke_reason
```

关键约束：

- Key 必须绑定一个研究用户和一个租户；
- Key 的工具权限必须是租户工具策略的子集；
- Key 不能通过自身扩大租户权限；
- 用户、Membership、租户或 Key 任一被停用，访问立即失败；
- 修改 Key 权限后立即生效，不要求重新生成；
- Key 的配额覆盖值只能比租户上限更严格，不能绕过租户总配额。

---

## 5. 管理员操作流程

### 5.1 一体化创建向导

在 `租户 → 用户与 Access Keys` 中提供“添加研究用户”按钮。

向导只显示管理员真正需要理解的字段：

1. 用户名称；
2. 邮箱或备注，可选；
3. 所属团队，可选；
4. 允许使用的 Scholar 工具；
5. 配额或速率限制；
6. Key 名称，例如“张三的笔记本”；
7. 有效期。

提交后在一个事务中完成：

1. 创建 `managed_researcher`；
2. 创建该租户的 active Membership；
3. 创建 Access Key；
4. 写入审计日志；
5. 返回只显示一次的完整 Key。

创建完成页提供：

- 复制 Access Key；
- 复制 DSH 配置命令；
- 下载不含其他敏感信息的接入说明；
- “我已保存”确认。

### 5.2 Key 管理页

每个用户显示：

- 用户状态；
- Key 名称；
- Key 前缀和末四位；
- 工具权限摘要；
- 已用配额；
- 最后使用时间；
- 到期时间；
- active、expired 或 revoked 状态。

支持：

- 生成新 Key；
- 修改工具权限；
- 修改更严格的配额；
- 修改到期时间；
- 立即撤销；
- 轮换 Key；
- 停用用户并使其全部 Key 立即失效。

不允许再次查看完整 Key；遗失后只能生成新 Key。

---

## 6. DSH 用户操作流程

### 6.1 建立 SSH 隧道

用户继续使用独立 SSH 账号或独立 SSH public key：

```sh
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:9845:127.0.0.1:8081 \
  <ssh-user>@<proxy-host>
```

每个用户的 SSH key 应可独立撤销。

服务器应限制该 SSH 身份：

- 仅允许指定端口转发；
- 禁止交互 shell；
- 禁止 PTY；
- 禁止 agent forwarding；
- 禁止 X11 forwarding；
- 不允许绑定 `0.0.0.0`；
- 不允许使用 SSH `-g` 暴露本地转发端口。

### 6.2 保存 Access Key

推荐命令：

```sh
scholar gateway-login \
  --gateway http://127.0.0.1:9845/v1/mcp/scholar
```

CLI 隐藏提示：

```text
请输入 Scholar Access Key:
```

自动化环境使用：

```sh
printf '%s\n' "$SCHOLAR_ACCESS_KEY" |
  scholar gateway-login \
  --api-key-stdin \
  --gateway http://127.0.0.1:9845/v1/mcp/scholar
```

DSH 行为：

1. 校验 gateway 是 HTTPS 或 numeric loopback HTTP；
2. 隐藏读取 Access Key；
3. 可调用轻量验证端点确认 Key 有效；
4. 将 Key 写入 DSH managed credential；
5. Scholar MCP 配置引用该 managed credential；
6. 后续请求直接发送：

```http
Authorization: Bearer sk_scholar_...
```

不再调用 `/v1/session`，也不再兑换 capability。

---

## 7. 权限模型

管理员控制每个 Key：

### 基础权限

- 绑定哪个租户；
- 允许哪些 Scholar 工具；
- 是否允许写操作；
- 可访问哪些数据集或项目（未来可选）。

### 用量控制

- 每分钟请求数；
- 每日或每月调用量；
- token、计算量或成本额度；
- 并发请求上限。

### 生命周期

- 生效时间；
- 到期时间；
- active/revoked 状态；
- 最后使用时间；
- 撤销原因。

实际允许调用的工具应按交集计算：

```text
Key allowed_tools
∩ Tenant tool policy
∩ Backend available_tools
```

任何一层不允许，调用都应被拒绝。

---

## 8. 有效期建议

为了接近常见 LLM API Key 的体验：

- 默认有效期：90 天；
- 可选：30 天、90 天、365 天；
- 小型可信实验室可允许“长期有效”，但后台必须明确风险；
- 长期 Key 仍必须支持立即撤销和轮换；
- 每台设备独立 Key，不要多人共享一个 Key。

不再使用当前默认 1 小时 capability，否则用户体验仍然复杂。

轮换流程：

1. 生成新 Key；
2. 新旧 Key 短暂并存；
3. 用户更新 DSH；
4. 管理员撤销旧 Key。

---

## 9. 撤权行为

### 撤销单个设备

撤销对应 Access Key，其他设备不受影响。

### 禁止某个用户

把研究用户设为 disabled，该用户所有 Key 立即失效。

### 移出某个租户

停用 Membership，该用户在该租户下的所有 Key 立即失效。

### 禁止所有研究用户

停用租户，租户下全部 Key 立即失效。

### 禁止建立隧道

撤销该用户的 SSH public key 或服务器 SSH 账号。

Proxy Hub API 权限和 SSH 准入相互独立；两者任一关闭都可以阻止访问。

---

## 10. 推荐 API

### 研究用户

```http
POST   /v1/admin/tenants/{tenant_id}/researchers
GET    /v1/admin/tenants/{tenant_id}/researchers
GET    /v1/admin/researchers/{principal_id}
PATCH  /v1/admin/researchers/{principal_id}
```

### Access Key

```http
POST   /v1/admin/researchers/{principal_id}/access-keys
GET    /v1/admin/researchers/{principal_id}/access-keys
GET    /v1/admin/access-keys/{key_id}
PATCH  /v1/admin/access-keys/{key_id}
POST   /v1/admin/access-keys/{key_id}/revoke
POST   /v1/admin/access-keys/{key_id}/rotate
```

只有创建或轮换响应返回一次完整 Key：

```json
{
  "id": "access_key_...",
  "access_key": "sk_scholar_v1_...",
  "display": "sk_scholar_v1_...7A9F",
  "expires_at": "2026-12-02T00:00:00Z"
}
```

### DSH 验证

可增加：

```http
GET /v1/access-key/me
```

返回：

- 用户显示名；
- 租户；
- Key 状态；
- 到期时间；
- 可用工具；
- 配额摘要。

不得返回密钥本身或后端 credential。

---

## 11. Proxy Hub 请求鉴权

收到 MCP 请求后：

1. 读取 Bearer token；
2. 判断是否为 `sk_scholar_` Access Key；
3. 计算 token digest 并查找 Key；
4. 检查 Key 未撤销、未过期；
5. 检查研究用户 active；
6. 检查租户 active；
7. 检查 Membership active；
8. 计算最终工具权限交集；
9. 执行 Key 和租户配额；
10. 选择 Scholar backend；
11. 服务端注入 backend credential；
12. 记录 key_id、principal_id、tenant_id、tool、结果和用量；
13. 更新 `last_used_at`。

认证失败时只返回通用错误，不泄露 Key 是否存在、用户状态或租户信息。

---

## 12. 与当前实现的关系

### 保留

- Dex/OIDC 管理员登录；
- Principal；
- Tenant；
- Membership；
- Team；
- 租户工具策略；
- 配额；
- 审计；
- Scholar backend route；
- 服务端 credential injection；
- MCP gateway；
- DSH managed credential；
- SSH loopback 安全限制。

### 简化或移除

- 普通研究用户不再经过 Dex；
- 后台不再要求管理员手填 Principal ID；
- 不再把 Role Binding 用于普通 DSH 用户；
- 不再给新用户签发一次性 enrolment code；
- DSH 不再调用 `/v1/session` 兑换 capability；
- 不再使用默认 1 小时 capability 作为日常凭据。

### 可复用

现有 `DshCapability` 的很多字段和鉴权逻辑可以复用：

- principal_id；
- tenant_id；
- scopes；
- expires_at；
- revoked_at；
- last_used_at；
- token digest；
- Principal/Tenant/Membership 状态检查。

因此不需要重写整个网关，只需把它演进为长期可管理的 Access Key。

---

## 13. 兼容迁移计划

### 第一批：后端双栈

- 给 Principal 增加 `kind`；
- 支持管理员创建 managed researcher；
- 增加 Access Key 表或扩展 capability 表；
- MCP gateway 同时接受旧 capability 和新 Access Key；
- 增加 Key 列表、修改、撤销和轮换 API；
- 增加审计事件；
- 暂时保留 enrolment 和 `/v1/session`。

### 第二批：管理后台

- 把“身份主体 ID + Membership + Enrolment”拆散流程替换为一个向导；
- 新增“研究用户与 Access Keys”页面；
- 创建成功只显示一次 Key；
- 增加权限编辑、配额、到期、撤销和轮换；
- Dex Principal 页面只面向管理员身份管理。

### 第三批：DSH

- `gateway-login` 改为读取 Access Key；
- 支持 `--api-key-stdin`；
- 直接保存 Key 到 managed credential；
- 移除新流程对 `/v1/session` 的依赖；
- 更新中英文安装和 SSH 隧道文档；
- 保留旧 enrolment 登录一段兼容期。

### 第四批：淘汰旧链路

- 为现有用户签发新 Access Key；
- 等待旧 capability 到期；
- 关闭新 enrolment 创建；
- 将旧 API 标记 deprecated；
- 确认没有旧客户端后再删除 enrolment UI/API；
- 保留必要的历史审计记录。

迁移期间不得使现有 DSH 用户突然失效。

---

## 14. 第一版不需要做的复杂功能

为了保持简单，第一版不需要：

- OAuth device flow；
- refresh token；
- JWT；
- Key 自助门户；
- 用户自己申请权限；
- 复杂 RBAC；
- 每个用户登录 Proxy Hub；
- 自动 SSH 账号管理；
- 跨租户 Key；
- 多级组织结构。

第一版只需：

```text
管理员创建用户和 Key
→ 用户保存 Key
→ Proxy Hub 检查权限
→ 管理员可随时撤销
```

---

## 15. 验收标准

### 管理员

- 能在一个向导内创建研究用户和首个 Key；
- 不需要手填 Principal ID；
- 能给每个 Key 设置工具权限、配额和有效期；
- 完整 Key 只显示一次；
- 能查看使用状态；
- 能立即撤销或轮换；
- 停用用户后全部 Key 立即失效。

### 用户

- 不需要 Dex 账号；
- 不需要打开控制台；
- 不需要理解 Principal、Membership、Role 或 capability；
- 只需建立 SSH 隧道并输入一次 Access Key；
- DSH 重启后仍可通过 managed credential 使用；
- Key 被撤销或到期后获得清晰但不泄密的错误提示。

### 安全

- 数据库、日志和审计中没有明文 Key；
- Key 权限不能超过租户策略；
- SSH 隧道不能绕过 Proxy Hub 鉴权；
- 研究用户无法登录管理控制台；
- 禁用用户、Membership、租户或 Key 均能立即阻止请求；
- Scholar backend credential 永不下发到 DSH。

---

## 16. 最终推荐

采用下面这一条主流程：

```text
管理员：
Dex 登录 → 创建研究用户 → 设置权限 → 生成 Access Key

用户：
建立 SSH 隧道 → DSH 输入 Access Key → 直接使用 Scholar
```

这保留了 Proxy Hub 的多租户、权限、配额、审计、撤销和后端 credential 隔离，同时把普通用户接入体验简化为与常见 LLM API Key 基本一致。
