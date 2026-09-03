import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type Lang = "en" | "zh";

const STORAGE_KEY = "proxy_hub_lang";

const ZH: Record<string, string> = {
  // ── chrome ──
  "Overview": "总览",
  "Tenants": "租户",
  "Backends": "后端",
  "Audit": "审计",
  "Usage": "用量",
  "Principals": "身份主体",
  "Guide": "引导指南",
  "Operations": "运营",
  "Identity": "身份",
  "Loading control plane": "控制面加载中",
  "Operator access": "管理员访问",
  "Sign in through the configured identity provider to manage Proxy Hub.":
    "通过已配置的身份提供方登录，以管理 Proxy Hub。",
  "Sign in with OIDC": "使用 OIDC 登录",
  "Access denied": "访问被拒绝",
  "Control plane unavailable": "控制面不可用",
  "The administration API is unavailable.": "管理 API 不可用。",
  "Retry": "重试",
  "Return to overview": "返回总览",
  "This browser session does not advertise the capability for this page.":
    "当前会话不具备访问该页面的能力（capability）。",
  "No records": "暂无记录",
  "Nothing to show.": "没有可显示的内容。",
  "Loading server data…": "正在加载服务器数据…",
  "Service unavailable": "服务不可用",
  "Cancel": "取消",
  "Submitting…": "提交中…",
  "Operational": "运行中",
  "Disabled": "已停用",
  "Request": "请求",
  "Close": "关闭",
  "Dismiss server response": "关闭提示",
  "Switch to English": "Switch to English",
  "Switch to Chinese": "切换到中文",

  // ── overview ──
  "CONTROL PLANE": "控制面",
  "Operations overview": "运营总览",
  "Current health, tenant footprint, and routing readiness.":
    "当前健康状态、租户覆盖与路由就绪情况。",
  "Observed": "观测于",
  "Visible tenants": "可见租户",
  "Within your assigned scope": "在您的授权范围内",
  "Recent failures": "近期失败",
  "No active incidents reported": "暂无进行中的故障",
  "Review audit decisions": "请查看审计判定",
  "Tenant activity": "租户动态",
  "Recently updated": "最近更新",
  "View all": "查看全部",
  "No tenants in scope": "范围内没有租户",
  "A platform administrator can create the first tenant.":
    "平台管理员可以创建第一个租户。",
  "Read the setup guide": "阅读配置指南",
  "Welcome to Proxy Hub": "欢迎使用 Proxy Hub",
  "overview.welcome.body":
    "这是 Scholar 学术平台的多租户管理后台。第一次使用？按「引导指南」八步完成配置：建租户 → 拉成员 → 配策略/配额 → 注册后端 → 探测激活 → 绑路由 → 发兑换码 → 队友接入。",

  // ── tenants ──
  "ACCESS BOUNDARIES": "访问边界",
  "Manage organization boundaries and their Scholar routing scope.":
    "管理组织边界及其 Scholar 路由范围。",
  "New tenant": "新建租户",
  "Create tenant": "创建租户",
  "Tenant created.": "租户已创建。",
  "Tenant": "租户",
  "Status": "状态",
  "Version": "版本",
  "Updated": "更新时间",
  "Tenant slug is required.": "租户标识不能为空。",
  "Tenant name is required.": "租户名称不能为空。",
  "Teams": "团队",
  "Members": "成员",
  "Role bindings": "角色绑定",
  "Add team": "添加团队",
  "Add member": "添加成员",
  "Add role binding": "添加角色绑定",
  "Team created.": "团队已创建。",
  "Member added.": "成员已添加。",
  "Role binding added.": "角色绑定已添加。",
  "Remove": "移除",
  "No teams yet.": "还没有团队。",
  "No members yet.": "还没有成员。",
  "No role bindings yet.": "还没有角色绑定。",

  // ── tenants page ──
  "Manage this tenant's identity, policy, quota, and Scholar routing boundaries.":
    "管理该租户的身份、策略、配额与 Scholar 路由边界。",
  "Loading tenant…": "租户加载中…",
  "Summary": "概要",
  "Teams & memberships": "团队与成员",
  "Policy, quota & route": "策略、配额与路由",
  "Tenant slugs are stable identifiers and cannot be changed.":
    "租户 slug 是稳定标识，创建后不可修改。",
  "Slug": "标识（slug）",
  "No tenants available": "暂无可用租户",
  "Create the first tenant to establish a policy and corpus boundary.":
    "创建第一个租户以建立策略与语料边界。",
  "No tenants are assigned to this session.": "当前会话未被分配任何租户。",
  "Tenant identity": "租户身份",
  "Resource ID": "资源 ID",
  "Last updated": "最后更新",
  "Disable tenant": "停用租户",
  "Enable tenant": "启用租户",
  "Security boundary": "安全边界",
  "Fail-closed administration": "默认拒绝的管理面",
  "Browser capabilities control presentation only. The Proxy Hub API independently enforces role, tenant scope, CSRF, ETag, and idempotency requirements on every mutation.":
    "浏览器端能力仅控制界面展示。Proxy Hub API 会在每次变更操作上独立校验角色、租户范围、CSRF、ETag 与幂等性。",

  // ── tenant access ──
  "Organization": "组织",
  "New team": "新建团队",
  "No teams": "暂无团队",
  "Create an optional team boundary.": "可选创建团队分组边界。",
  "Tenant access": "租户访问",
  "No memberships": "暂无成员",
  "Add an active principal to this tenant.": "将一个已激活的身份主体加入本租户。",
  "Tenant-wide": "全租户",
  "Enable": "启用",
  "Authorization": "授权",
  "Bind role": "绑定角色",
  "No active bindings": "暂无生效的角色绑定",
  "Bind a tenant role to an active member.": "将租户角色绑定给一位在册成员。",
  "Create team": "创建团队",
  "Teams create an optional grouping boundary inside this tenant.":
    "团队是租户内的可选分组边界。",
  "Team name": "团队名称",
  "Add membership": "添加成员",
  "The principal must already be active. Team assignment is optional.":
    "身份主体须已激活。团队为可选。",
  "Principal ID": "身份主体 ID",
  "The principal must have an active membership in this tenant.":
    "身份主体须持有本租户的有效成员身份。",
  "Tenant admin": "租户管理员",
  "Operator": "运营者",
  "Auditor": "审计员",

  // ── policies ──
  "Deny by default": "默认拒绝",
  "Tool policy": "工具策略",
  "Save exact allowlist": "保存精确白名单",
  "Request enforcement": "请求强制",
  "Quota policy": "配额策略",
  "Quota class": "配额等级",
  "Request limit": "请求上限",
  "Period seconds": "统计周期（秒）",
  "Concurrency limit": "并发上限",
  "Enforce request and concurrency limits": "强制执行请求与并发限制",
  "Save quota": "保存配额",
  "Explicit affinity": "显式路由绑定",
  "Backend route": "后端路由",
  "Scholar backend": "Scholar 后端",
  "Select backend": "选择后端",
  "Route status": "路由状态",
  "Save route": "保存路由",
  "Corpus": "语料",
  "No explicit route is configured.": "尚未配置显式路由。",
  "Saving…": "保存中…",
  "Backend": "后端",

  // ── backends ──
  "SCHOLAR DATA PLANE": "SCHOLAR 数据面",
  "Scholar routing": "Scholar 路由",
  "Backend registry": "后端注册表",
  "Register Scholar services, verify readiness, and rotate deployer-owned credential references.":
    "注册 Scholar 服务、校验就绪状态并轮换部署方持有的凭据引用。",
  "Register backend": "注册后端",
  "Probe": "探测",
  "Probe now": "立即探测",
  "Probe readiness": "探测就绪状态",
  "Activate": "激活",
  "Rotate credential": "轮换凭据",
  "Register": "注册",
  "Backend registered.": "后端已注册。",
  "Probe complete.": "探测完成。",
  "Backend activated.": "后端已激活。",
  "Backend disabled.": "后端已停用。",
  "Credential rotated.": "凭据已轮换。",
  "base url": "基础 URL",
  "corpus version": "语料库版本",
  "credential reference": "凭据引用",
  "credential version": "凭据版本",
  "Backend name is required.": "后端名称不能为空。",
  "Base URL": "基础 URL",
  "Base URL is required.": "基础 URL 不能为空。",
  "Corpus version": "语料库版本",
  "Corpus version is required.": "语料库版本不能为空。",
  "Credential reference": "凭据引用",
  "Credential reference is required.": "凭据引用不能为空。",
  "Credential version": "凭据版本",
  "Readiness": "就绪状态",
  "Capacity": "容量",
  "parsed papers": "已解析论文",
  "vector chunks": "向量块",
  "graph built at": "图构建时间",
  "No Scholar backends": "暂无 Scholar 后端",
  "Register a backend before configuring tenant routes.":
    "请先注册后端，再配置租户路由。",
  "Backend detail": "后端详情",
  "Service URL": "服务 URL",
  "Unversioned": "未标注版本",
  "Not probed": "未探测",
  "never": "从未",
  "Edit registration": "编辑注册信息",
  "Rotate credential reference": "轮换凭据引用",
  "this backend?": "该后端？",
  "Disable backend": "停用后端",
  "Activate backend": "激活后端",
  "Register Scholar backend": "注册 Scholar 后端",
  "Only env:NAME credential references are accepted. Secret material stays outside the Hub database.":
    "仅接受 env:NAME 形式的凭据引用。密钥本体不会进入 Hub 数据库。",
  "New credential reference": "新凭据引用",
  "The existing readiness result will be invalidated until the backend is probed again.":
    "现有就绪结果将失效，直到重新探测后端。",
  "Rotate reference": "轮换引用",
  "Edit backend registration": "编辑后端注册",
  "Changing service or corpus identity invalidates the previous readiness result.":
    "修改服务或语料标识会使之前的就绪结果失效。",
  "Save registration": "保存注册信息",

  // ── audit ──
  "Bounded observability": "有界可观测",
  "AUDIT TRAIL": "审计追踪",
  "Audit events": "审计事件",
  "Review minimized authorization decisions.": "查看脱敏后的授权决策记录。",
  "Authorization and operational metadata from the last 24 hours. Research content, request bodies, digests, and credentials are never returned.":
    "最近 24 小时的授权与运营元数据。研究内容、请求体、摘要与凭据永不返回。",
  "Scope": "范围",
  "All tenants": "全部租户",
  "No audit events": "暂无审计事件",
  "No bounded operational events were recorded in this scope.":
    "该范围内没有记录在案的有界运营事件。",
  "Occurred": "发生时间",
  "Action": "操作",
  "Outcome": "结果",
  "Tool": "工具",
  "Decision": "判定",
  "Tenant / resource": "租户 / 资源",
  "Latency": "延迟",
  "Next page": "下一页",
  "Time": "时间",

  // ── usage ──
  "Immutable reporting": "只读报表",
  "USAGE": "用量",
  "Inspect quota consumption per tenant.": "查看各租户的配额消耗。",
  "Request outcomes, latency, returned bytes, and quota consumption for the last 24 hours. Reporting never changes quota counters.":
    "最近 24 小时的请求结果、延迟、返回字节与配额消耗。报表不会改动配额计数。",
  "Gateway calls in range": "区间内的网关调用",
  "Failed or rejected": "失败或被拒",
  "Bounded result classes": "有界结果分类",
  "Returned bytes": "返回字节",
  "Model-visible response bytes": "模型可见的响应字节",
  "No usage rows": "暂无用量数据",
  "No tenants are available in this reporting scope.":
    "该报表范围内没有可用租户。",
  "Requests": "请求数",
  "Outcomes": "结果",
  "Quota": "配额",
  "Limit": "上限",
  "Window": "窗口",

  // ── principals ──
  "PRINCIPALS": "身份主体",
  "Identity administration": "身份管理",
  "Directory of operator identities provisioned by sign-in.":
    "由登录自动登记的管理员身份目录。",
  "Control login eligibility. Memberships and role bindings remain tenant-scoped resources.":
    "控制登录资格。成员身份与角色绑定仍属租户域资源。",
  "No principals": "暂无身份主体",
  "Principals appear after the identity provider establishes them.":
    "身份主体由身份提供方建立后才会出现在这里。",
  "Subject": "主体标识",
  "Display name": "显示名",
  "Roles": "角色",
  "Created": "创建时间",
  "Issuer / subject": "签发方 / 主体",

  // ── enrolments ──
  "ACCESS": "访问控制",
  "Enrolments": "兑换码",
  "Issue enrolment": "发放兑换码",
  "Issue": "发放",
  "Enrolment issued.": "兑换码已发放。",
  "Revoke": "撤销",
  "Enrolment revoked.": "兑换码已撤销。",
  "principal": "身份主体",
  "scopes": "授权工具",
  "expires in (seconds)": "有效期（秒）",
  "enrolment token": "兑换码",
  "Copy the enrolment token now; it is shown only once.":
    "请立即复制兑换码，它只会显示这一次。",
  "session label": "会话标签",
  "Sessions": "会话",
  "Revoke sessions": "撤销会话",
  "Sessions revoked.": "会话已撤销。",

  // ── guide ──
  "Setup guide": "配置指南",
  "Follow these steps to onboard a tenant from zero to a working DSH capability.":
    "按以下步骤把一个租户从零配到队友可用。",
  "guide.step1.title": "① 创建租户",
  "guide.step1.body":
    "在「租户」页点「新建租户」，填写 slug（英文标识，如 scholar-lab）与名称。租户是隔离边界：工具、配额、路由都挂在租户上。",
  "guide.step2.title": "② 拉入成员",
  "guide.step2.body":
    "队友首次 OIDC 登录后会自动出现在「身份主体」。回到租户详情 → 团队与成员 → 添加成员（填其身份主体 ID）。可选：先建团队再把成员归组。",
  "guide.step3.title": "③ 配置工具策略与配额",
  "guide.step3.body":
    "租户详情 → 策略、配额与路由：工具策略默认全拒，勾选要放行的工具（只读起步建议勾 10 个 read 类工具）；配额按需设置每小时请求上限与并发上限，并勾选强制执行。",
  "guide.step4.title": "④ 注册 Scholar 后端",
  "guide.step4.body":
    "「后端」页 → 注册后端：基础 URL 填数据面地址、语料库版本填 readiness 端点报告的版本、凭据引用填 env:SCHOLAR_SERVICE_TOKEN。",
  "guide.step5.title": "⑤ 探测并激活",
  "guide.step5.body":
    "注册后先「探测就绪状态」（读取 readiness，校验语料版本一致），成功后「激活后端」。修改 URL 或语料版本会使探测失效，需重新探测再激活。",
  "guide.step6.title": "⑥ 绑定租户路由",
  "guide.step6.body":
    "租户详情 → 策略、配额与路由 → 后端路由：选择目标后端与语料版本，保存并激活。此后该租户的所有 MCP 调用都路由到这个后端。",
  "guide.step7.title": "⑦ 发放兑换码",
  "guide.step7.body":
    "租户详情 → 访问控制 → 兑换码 → 发放：选成员、勾授权工具（不得超过工具策略白名单）、设有效期。兑换码只显示一次，请私发给队友。",
  "guide.step8.title": "⑧ 队友接入",
  "guide.step8.body":
    "队友安装 scholar-dsh-bundle（Release 下载）后运行 scholar gateway-login --code <兑换码>，即可在 dsh 学术模式里经网关使用全部授权工具。到期前向管理员要新码重跑即可，配置无需改动。",
  "guide.tip.title": "日常运维",
  "guide.tip.body":
    "「审计」看每次调用的脱敏记录；「用量」看配额水位；人员离职 = 撤销其兑换码/会话（连坐清理会话）。语料更新后到「后端」重新探测并激活。",
};

interface I18nValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: string) => string;
}

const I18nContext = createContext<I18nValue | null>(null);

function initialLang(): Lang {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "zh" || stored === "en") {
      return stored;
    }
  } catch {
    // storage unavailable; fall through to browser language
  }
  return navigator.language?.toLowerCase().startsWith("zh") ? "zh" : "en";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // storage unavailable; keep in-memory only
    }
  }, []);

  const t = useCallback(
    (key: string) => (lang === "zh" ? (ZH[key] ?? key) : key),
    [lang],
  );

  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext);
  if (!value) {
    throw new Error("useI18n must be used inside I18nProvider");
  }
  return value;
}

export function statusLabel(status: string, t: (key: string) => string): string {
  if (status === "active" || status === "ready") {
    return t("Operational");
  }
  if (status === "disabled") {
    return t("Disabled");
  }
  return status.replaceAll("_", " ");
}

export function LanguageToggle() {
  const { lang, setLang, t } = useI18n();
  const next = lang === "zh" ? "en" : "zh";
  return (
    <button
      className="lang-toggle"
      onClick={() => setLang(next)}
      title={lang === "zh" ? t("Switch to English") : t("Switch to Chinese")}
    >
      {lang === "zh" ? "EN" : "中文"}
    </button>
  );
}
