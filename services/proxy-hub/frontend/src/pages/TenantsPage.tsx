import { useCallback, useEffect, useState } from "react";

import { api, ApiError } from "../api";
import {
  EmptyState,
  InlineAlert,
  Modal,
  PageHeader,
  ServerNotice,
  StatusPill,
  SubmitActions,
  navigate,
} from "../components";
import type {
  AdminMe,
  ResourceState,
  Tenant,
  TenantCreate,
} from "../types";
import { TenantAccess } from "./TenantAccess";
import { TenantPolicies } from "./TenantPolicies";

export type TenantSection = "summary" | "access" | "policies";

export interface TenantRouteMatch {
  tenantId: string | null;
  section: TenantSection;
}

export function tenantRouteFromPath(path: string): TenantRouteMatch {
  const match = path.match(
    /^\/console\/tenants\/([^/]+)(?:\/(access|policies))?\/?$/,
  );
  return {
    tenantId: match?.[1] ? decodeURIComponent(match[1]) : null,
    section:
      match?.[2] === "access" || match?.[2] === "policies"
        ? match[2]
        : "summary",
  };
}

function tenantPath(tenantId: string, section: TenantSection): string {
  const base = `/console/tenants/${encodeURIComponent(tenantId)}`;
  return section === "summary" ? base : `${base}/${section}`;
}

export function TenantsPage({
  me,
  tenants,
  route,
  onReload,
}: {
  me: AdminMe;
  tenants: Tenant[];
  route: TenantRouteMatch;
  onReload: () => Promise<void>;
}) {
  const [detail, setDetail] = useState<ResourceState<Tenant> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [busy, setBusy] = useState(false);

  const canCreate = me.capabilities.includes("tenant:create");
  const canUpdate = me.capabilities.includes("tenant:update");
  const canManageAccess = me.capabilities.includes("membership:manage");
  const canViewPolicies =
    me.capabilities.includes("policy:manage") ||
    me.capabilities.includes("quota:manage") ||
    me.capabilities.includes("route:manage") ||
    me.capabilities.includes("backend:read");

  const loadDetail = useCallback(async () => {
    if (!route.tenantId) {
      setDetail(null);
      return;
    }
    setDetail(null);
    setError(null);
    try {
      const result = await api.get<Tenant>(
        `/v1/admin/tenants/${encodeURIComponent(route.tenantId)}`,
      );
      if (!result.etag) {
        throw new Error("The tenant response did not include an ETag.");
      }
      setDetail({ data: result.data, etag: result.etag });
    } catch (loadError) {
      setError(
        loadError instanceof ApiError
          ? loadError.message
          : "Tenant details unavailable.",
      );
    }
  }, [route.tenantId]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  async function createTenant(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload: TenantCreate = {
      name: String(form.get("name") ?? "").trim(),
      slug: String(form.get("slug") ?? "").trim(),
    };
    setBusy(true);
    setError(null);
    try {
      const result = await api.post<Tenant>("/v1/admin/tenants", payload, {
        "Idempotency-Key": crypto.randomUUID(),
      });
      setShowCreate(false);
      setNotice(
        `Server created tenant ${result.data.name}, v${result.data.version}, ${result.data.status}.`,
      );
      await onReload();
      navigate(tenantPath(result.data.id, "summary"));
    } catch (mutationError) {
      setError(
        mutationError instanceof ApiError
          ? mutationError.message
          : "Tenant creation failed.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function toggleTenantStatus() {
    if (!detail) {
      return;
    }
    const status = detail.data.status === "active" ? "disabled" : "active";
    if (!window.confirm(`${status === "active" ? "Enable" : "Disable"} this tenant?`)) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await api.patch<Tenant>(
        `/v1/admin/tenants/${encodeURIComponent(detail.data.id)}`,
        { status },
        detail.etag,
      );
      if (!result.etag) {
        throw new Error("The tenant mutation did not include an ETag.");
      }
      setDetail({ data: result.data, etag: result.etag });
      setNotice(
        `Server returned tenant ${result.data.name}, v${result.data.version}, ${result.data.status}.`,
      );
      await onReload();
    } catch (mutationError) {
      setError(
        mutationError instanceof ApiError
          ? mutationError.message
          : "Tenant update failed.",
      );
      if (mutationError instanceof ApiError && mutationError.status === 412) {
        await loadDetail();
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Access boundaries"
        title={detail ? detail.data.name : "Tenants"}
        description={
          detail
            ? "Manage this tenant's identity, policy, quota, and Scholar routing boundaries."
            : "Manage organization boundaries and their Scholar routing scope."
        }
        action={
          !route.tenantId && canCreate
            ? { label: "New tenant", onClick: () => setShowCreate(true) }
            : undefined
        }
      />
      {notice ? (
        <ServerNotice message={notice} onClose={() => setNotice(null)} />
      ) : null}
      {error ? <InlineAlert message={error} /> : null}
      {!route.tenantId ? (
        <TenantList tenants={tenants} canCreate={canCreate} />
      ) : !detail ? (
        error ? null : <section className="panel detail-loading">Loading tenant…</section>
      ) : (
        <>
          <div className="subnav" aria-label="Tenant sections">
            <button
              className={route.section === "summary" ? "active" : undefined}
              onClick={() => navigate(tenantPath(detail.data.id, "summary"))}
            >
              Summary
            </button>
            {canManageAccess ? (
              <button
                className={route.section === "access" ? "active" : undefined}
                onClick={() => navigate(tenantPath(detail.data.id, "access"))}
              >
                Teams & memberships
              </button>
            ) : null}
            {canViewPolicies ? (
              <button
                className={route.section === "policies" ? "active" : undefined}
                onClick={() => navigate(tenantPath(detail.data.id, "policies"))}
              >
                Policy, quota & route
              </button>
            ) : null}
            <button
              className="back-link"
              onClick={() => navigate("/console/tenants")}
            >
              All tenants
            </button>
          </div>
          {route.section === "access" && canManageAccess ? (
            <TenantAccess tenantId={detail.data.id} />
          ) : route.section === "policies" && canViewPolicies ? (
            <TenantPolicies tenantId={detail.data.id} me={me} />
          ) : (
            <TenantSummary
              tenant={detail.data}
              canUpdate={canUpdate}
              busy={busy}
              onToggle={() => void toggleTenantStatus()}
            />
          )}
        </>
      )}
      {showCreate ? (
        <Modal
          title="Create tenant"
          description="Tenant slugs are stable identifiers and cannot be changed."
          onClose={() => setShowCreate(false)}
        >
          <form onSubmit={(event) => void createTenant(event)}>
            <label>
              Display name
              <input name="name" required maxLength={200} autoFocus />
            </label>
            <label>
              Slug
              <input
                name="slug"
                required
                minLength={3}
                maxLength={64}
                pattern="[a-z0-9][a-z0-9-]+[a-z0-9]"
                placeholder="research-platform"
              />
            </label>
            <SubmitActions
              busy={busy}
              submitLabel="Create tenant"
              onCancel={() => setShowCreate(false)}
            />
          </form>
        </Modal>
      ) : null}
    </>
  );
}

function TenantList({
  tenants,
  canCreate,
}: {
  tenants: Tenant[];
  canCreate: boolean;
}) {
  if (tenants.length === 0) {
    return (
      <section className="panel">
        <EmptyState
          title="No tenants available"
          message={
            canCreate
              ? "Create the first tenant to establish a policy and corpus boundary."
              : "No tenants are assigned to this session."
          }
        />
      </section>
    );
  }
  return (
    <section className="panel">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Tenant</th>
              <th>Status</th>
              <th>Version</th>
              <th>Updated</th>
              <th aria-label="Open" />
            </tr>
          </thead>
          <tbody>
            {tenants.map((tenant) => (
              <tr
                key={tenant.id}
                onClick={() => navigate(tenantPath(tenant.id, "summary"))}
              >
                <td>
                  <strong>{tenant.name}</strong>
                  <span>{tenant.slug}</span>
                </td>
                <td>
                  <StatusPill status={tenant.status} />
                </td>
                <td className="mono">v{tenant.version}</td>
                <td>{new Date(tenant.updated_at).toLocaleDateString()}</td>
                <td className="row-arrow">›</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function TenantSummary({
  tenant,
  canUpdate,
  busy,
  onToggle,
}: {
  tenant: Tenant;
  canUpdate: boolean;
  busy: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="summary-grid">
      <section className="panel summary-card">
        <span className="eyebrow">Tenant identity</span>
        <div className="summary-title">
          <h2>{tenant.name}</h2>
          <StatusPill status={tenant.status} />
        </div>
        <dl>
          <div>
            <dt>Slug</dt>
            <dd>{tenant.slug}</dd>
          </div>
          <div>
            <dt>Resource ID</dt>
            <dd className="mono">{tenant.id}</dd>
          </div>
          <div>
            <dt>Version</dt>
            <dd>{tenant.version}</dd>
          </div>
          <div>
            <dt>Last updated</dt>
            <dd>{new Date(tenant.updated_at).toLocaleString()}</dd>
          </div>
        </dl>
        {canUpdate ? (
          <button
            className={
              tenant.status === "active" ? "danger-button" : "primary-button"
            }
            disabled={busy}
            onClick={onToggle}
          >
            {tenant.status === "active" ? "Disable tenant" : "Enable tenant"}
          </button>
        ) : null}
      </section>
      <section className="panel summary-card">
        <span className="eyebrow">Security boundary</span>
        <h2>Fail-closed administration</h2>
        <p>
          Browser capabilities control presentation only. The Proxy Hub API
          independently enforces role, tenant scope, CSRF, ETag, and idempotency
          requirements on every mutation.
        </p>
      </section>
    </div>
  );
}
