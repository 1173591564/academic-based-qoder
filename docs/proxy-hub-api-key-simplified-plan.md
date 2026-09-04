# Proxy Hub 单实验室 Token 方案

本方案已经由 `docs/proxy-hub.md` 与 `docs/proxy-hub-console.md` 实现并取代旧的多租户 Access Key 向导设计。

## 用户流程

```text
管理员 OIDC 登录
  → 输入 Token 名称
  → 创建永久 Token
  → 复制一次性显示的 raw Token
  → 分发给研究用户

研究用户打开 DSH academic preset
  → 首次弹窗粘贴 Token
  → DSH 调用 /v1/me 验证
  → 保存为 SCHOLAR_REMOTE_TOKEN Managed Credential
  → 后续直接使用 16 个 Scholar MCP Tools
```

Token 名称是 API-Key-style label，例如“张三”“实验室电脑A”或“文献组”，不是登录用户名。Active Token 名称在 trim、NFKC normalization 与 case folding 后唯一。显示名称可以修改而不使 Token 失效。

新 Token 默认永久有效；rotation 或 revoke 使旧 Token 立即失效。服务端只保存 digest，完整 Token 只显示一次。Legacy Access Key 保留原有 expiry 与 quota 行为。

Console 仅包含 Token management、Service status 与 Audit log。Tenant、Membership、Role Binding、policy、quota、route、backend credential 与 enrolment UI 被移除，但内部数据模型保留一个兼容版本。

Proxy Hub 不把用户 Token 转发给 Scholar Backend，也不保存研究参数或正文。Audit log 只显示 Token 名称、MCP Tool、时间、结果、latency 与 Request ID，并在 180 天后自动清理。

公网 HTTP 仅用于显式 development 配置，会明文暴露 Token 与研究请求。Production 必须使用 HTTPS 或加密私网。
