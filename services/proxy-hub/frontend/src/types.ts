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

export interface Tenant {
  id: string;
  slug: string;
  name: string;
  status: "active" | "disabled";
  version: number;
  created_at: string;
  updated_at: string;
}

export interface TenantList {
  items: Tenant[];
  next_cursor: string | null;
}

export interface TenantCreate {
  slug: string;
  name: string;
}

export interface TenantPatch {
  name?: string;
  status?: "active" | "disabled";
}
