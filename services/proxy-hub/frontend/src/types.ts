export interface Principal {
  id: string;
  email: string | null;
  display_name: string | null;
}

export interface RoleGrant {
  role: string;
  tenant_id: string | null;
}

export interface AdminMe {
  principal: Principal;
  roles: RoleGrant[];
  tenant_ids: string[];
  capabilities: string[];
}

export interface Overview {
  observed_at: string;
  control_plane: { status: string };
  tenants: { visible: number };
  recent_failures: Array<Record<string, unknown>>;
}

export interface Versioned {
  version: number;
  created_at: string;
  updated_at: string;
}

export interface Tenant extends Versioned {
  id: string;
  slug: string;
  name: string;
  status: "active" | "disabled";
}

export interface TenantList {
  items: Tenant[];
  next_cursor: string | null;
}

export interface TenantCreate {
  slug: string;
  name: string;
}

export interface Team extends Versioned {
  id: string;
  tenant_id: string;
  name: string;
  status: "active" | "disabled";
  etag: string;
}

export interface Membership extends Versioned {
  id: string;
  tenant_id: string;
  principal_id: string;
  team_id: string | null;
  status: "active" | "disabled";
  etag: string;
}

export interface RoleBinding extends Versioned {
  id: string;
  principal_id: string;
  tenant_id: string | null;
  role: string;
  revoked_at: string | null;
  etag: string;
}

export interface AdminPrincipal extends Versioned {
  id: string;
  issuer: string;
  subject: string;
  email: string | null;
  display_name: string | null;
  status: "active" | "disabled";
  etag: string;
}

export interface ManagedResearcher extends Versioned {
  id: string;
  display_name: string;
  email: string | null;
  kind: "managed_researcher";
  status: "active" | "disabled";
  membership_id: string;
  membership_status: "active" | "disabled";
  team_id: string | null;
  etag: string;
}

export interface ScholarAccessKey extends Versioned {
  id: string;
  access_key: string | null;
  principal_id: string;
  tenant_id: string;
  label: string;
  token_prefix: string;
  token_last_four: string;
  allowed_tools: string[];
  request_limit: number | null;
  period_seconds: number | null;
  status: "active" | "revoked" | "expired";
  expires_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
  revoke_reason: string | null;
  etag: string;
}

export interface ResearcherCreateResponse {
  researcher: ManagedResearcher;
  access_key: ScholarAccessKey;
}

export interface ToolPolicy extends Versioned {
  tenant_id: string;
  allowed_tools: string[];
}

export interface QuotaPolicy extends Versioned {
  tenant_id: string;
  quota_class: string;
  request_limit: number;
  period_seconds: number;
  concurrency_limit: number;
  enforcement_enabled: boolean;
}

export interface TenantRoute extends Versioned {
  tenant_id: string;
  backend_id: string;
  corpus_version: string;
  status: "active" | "disabled";
}

export interface BackendCredential {
  configured: boolean;
  version: string | null;
  rotated_at: string | null;
}

export interface BackendProbe {
  observed_at: string | null;
  ready: boolean | null;
  reason: string | null;
}

export interface ScholarBackend extends Versioned {
  id: string;
  name: string;
  base_url: string;
  corpus_version: string;
  status: "active" | "disabled";
  capacity: Record<string, string | number | boolean | null>;
  credential: BackendCredential;
  probe: BackendProbe;
}

export interface ListResponse<T> {
  items: T[];
  next_cursor?: string | null;
}

export interface AuditEvent {
  id: string;
  occurred_at: string;
  request_id: string;
  principal_id: string | null;
  tenant_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  outcome: string;
  tool_name: string | null;
  backend_id: string | null;
  corpus_version: string | null;
  decision: string | null;
  result_class: string | null;
  latency_ms: number | null;
  returned_bytes: number | null;
  quota_delta: number | null;
}

export interface QueryRange {
  from: string;
  to: string;
}

export interface AuditPage {
  items: AuditEvent[];
  next_cursor: string | null;
  range: QueryRange;
}

export interface UsageItem {
  tenant_id: string;
  requests: {
    total: number;
    successful: number;
    failed: number;
    rejected: number;
  };
  latency: {
    samples: number;
    average_ms: number | null;
    maximum_ms: number | null;
  };
  returned_bytes: number;
  quota: {
    consumed: number;
    configured: boolean;
    quota_class: string | null;
    request_limit: number | null;
    period_seconds: number | null;
    concurrency_limit: number | null;
    enforcement_enabled: boolean;
  };
}

export interface UsagePage {
  items: UsageItem[];
  next_cursor: string | null;
  range: QueryRange;
}

export interface ResourceState<T> {
  data: T;
  etag: string;
}
