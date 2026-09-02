import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { api, ApiError } from "./api";
import type {
  AdminMe,
  Overview,
  Tenant,
  TenantCreate,
  TenantList,
} from "./types";

type LoadState =
  | { kind: "loading" }
  | { kind: "unauthenticated" }
  | { kind: "denied"; message: string }
  | { kind: "unavailable"; message: string; requestId: string | null }
  | {
      kind: "ready";
      me: AdminMe;
      overview: Overview;
      tenants: Tenant[];
    };

interface TenantDetail {
  tenant: Tenant;
  etag: string;
}

function errorState(error: unknown): LoadState {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return { kind: "unauthenticated" };
    }
    if (error.status === 403) {
      return { kind: "denied", message: error.message };
    }
    return {
      kind: "unavailable",
      message: error.message,
      requestId: error.requestId,
    };
  }
  return {
    kind: "unavailable",
    message: "The administration API is unavailable.",
    requestId: null,
  };
}

function tenantIdFromPath(path: string): string | null {
  const match = path.match(/^\/console\/tenants\/([^/]+)$/);
  return match?.[1] ? decodeURIComponent(match[1]) : null;
}

function navigate(path: string): void {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function statusLabel(status: string): string {
  return status === "active" || status === "ready" ? "Operational" : "Disabled";
}

export function App() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [path, setPath] = useState(window.location.pathname);
  const [tenantDetail, setTenantDetail] = useState<TenantDetail | null>(null);
  const [tenantError, setTenantError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [mutatingTenant, setMutatingTenant] = useState(false);

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const me = await api.get<AdminMe>("/v1/admin/me");
      const [overview, tenants] = await Promise.all([
        api.get<Overview>("/v1/admin/overview"),
        api.get<TenantList>("/v1/admin/tenants"),
      ]);
      setState({
        kind: "ready",
        me: me.data,
        overview: overview.data,
        tenants: tenants.data.items,
      });
    } catch (error) {
      setState(errorState(error));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const onPopState = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const tenantId = tenantIdFromPath(path);

  useEffect(() => {
    if (!tenantId || state.kind !== "ready") {
      setTenantDetail(null);
      setTenantError(null);
      return;
    }
    let active = true;
    setTenantDetail(null);
    setTenantError(null);
    void api
      .get<Tenant>(`/v1/admin/tenants/${encodeURIComponent(tenantId)}`)
      .then((result) => {
        if (active && result.etag) {
          setTenantDetail({ tenant: result.data, etag: result.etag });
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setTenantError(
            error instanceof ApiError ? error.message : "Tenant details unavailable.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, [state.kind, tenantId]);

  const canCreateTenant =
    state.kind === "ready" && state.me.capabilities.includes("tenant:create");
  const canUpdateTenant =
    state.kind === "ready" && state.me.capabilities.includes("tenant:update");

  const principalLabel = useMemo(() => {
    if (state.kind !== "ready") {
      return "";
    }
    return (
      state.me.principal.display_name ??
      state.me.principal.email ??
      state.me.principal.id
    );
  }, [state]);

  async function createTenant(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload: TenantCreate = {
      name: String(form.get("name") ?? "").trim(),
      slug: String(form.get("slug") ?? "").trim(),
    };
    setCreating(true);
    setTenantError(null);
    try {
      const result = await api.post<Tenant>("/v1/admin/tenants", payload, {
        "Idempotency-Key": crypto.randomUUID(),
      });
      setShowCreate(false);
      await load();
      navigate(`/console/tenants/${encodeURIComponent(result.data.id)}`);
    } catch (error) {
      setTenantError(
        error instanceof ApiError ? error.message : "Tenant creation failed.",
      );
    } finally {
      setCreating(false);
    }
  }

  async function toggleTenantStatus() {
    if (!tenantDetail || mutatingTenant) {
      return;
    }
    const nextStatus =
      tenantDetail.tenant.status === "active" ? "disabled" : "active";
    const action = nextStatus === "disabled" ? "disable" : "enable";
    if (!window.confirm(`Confirm that you want to ${action} this tenant.`)) {
      return;
    }
    setMutatingTenant(true);
    setTenantError(null);
    try {
      const result = await api.patch<Tenant>(
        `/v1/admin/tenants/${encodeURIComponent(tenantDetail.tenant.id)}`,
        { status: nextStatus },
        tenantDetail.etag,
      );
      if (!result.etag) {
        throw new Error("The updated tenant response did not include an ETag.");
      }
      setTenantDetail({ tenant: result.data, etag: result.etag });
      await load();
    } catch (error) {
      setTenantError(
        error instanceof ApiError ? error.message : "Tenant update failed.",
      );
      if (error instanceof ApiError && error.status === 412 && tenantId) {
        const current = await api.get<Tenant>(
          `/v1/admin/tenants/${encodeURIComponent(tenantId)}`,
        );
        if (current.etag) {
          setTenantDetail({ tenant: current.data, etag: current.etag });
        }
      }
    } finally {
      setMutatingTenant(false);
    }
  }

  if (state.kind === "loading") {
    return <CenteredState title="Loading control plane" pulse />;
  }
  if (state.kind === "unauthenticated") {
    const returnTo = encodeURIComponent(window.location.pathname);
    return (
      <CenteredState
        title="Operator access"
        message="Sign in through the configured identity provider to manage Proxy Hub."
        action={{ label: "Sign in with OIDC", href: `/auth/login?return_to=${returnTo}` }}
      />
    );
  }
  if (state.kind === "denied") {
    return <CenteredState title="Access denied" message={state.message} />;
  }
  if (state.kind === "unavailable") {
    return (
      <CenteredState
        title="Control plane unavailable"
        message={state.message}
        requestId={state.requestId}
        action={{ label: "Retry", onClick: () => void load() }}
      />
    );
  }

  const onTenantsPage = path.startsWith("/console/tenants");

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">S</div>
          <div>
            <strong>Scholar</strong>
            <span>Proxy Hub</span>
          </div>
        </div>
        <nav aria-label="Primary navigation">
          <button
            className={!onTenantsPage ? "nav-item active" : "nav-item"}
            onClick={() => navigate("/console/")}
          >
            <span className="nav-icon">⌂</span>
            Overview
          </button>
          <button
            className={onTenantsPage ? "nav-item active" : "nav-item"}
            onClick={() => navigate("/console/tenants")}
          >
            <span className="nav-icon">◇</span>
            Tenants
          </button>
          <div className="nav-section">Operations</div>
          <button className="nav-item planned" disabled>
            <span className="nav-icon">↗</span>
            Backends
            <span className="soon">Next</span>
          </button>
          <button className="nav-item planned" disabled>
            <span className="nav-icon">≡</span>
            Audit
            <span className="soon">Next</span>
          </button>
        </nav>
        <div className="identity">
          <div className="avatar">{principalLabel.slice(0, 1).toUpperCase()}</div>
          <div>
            <strong>{principalLabel}</strong>
            <span>{state.me.roles[0]?.role.replaceAll("_", " ") ?? "No role"}</span>
          </div>
        </div>
      </aside>

      <main className="main">
        {onTenantsPage ? (
          <TenantsPage
            tenants={state.tenants}
            selectedId={tenantId}
            detail={tenantDetail}
            detailError={tenantError}
            canCreate={canCreateTenant}
            canUpdate={canUpdateTenant}
            showCreate={showCreate}
            creating={creating}
            mutating={mutatingTenant}
            onShowCreate={setShowCreate}
            onCreate={createTenant}
            onToggleStatus={() => void toggleTenantStatus()}
          />
        ) : (
          <OverviewPage overview={state.overview} tenants={state.tenants} />
        )}
      </main>
    </div>
  );
}

function OverviewPage({
  overview,
  tenants,
}: {
  overview: Overview;
  tenants: Tenant[];
}) {
  return (
    <>
      <PageHeader
        eyebrow="Control plane"
        title="Operations overview"
        description="Current health, tenant footprint, and routing readiness."
      />
      <section className="metric-grid">
        <MetricCard
          label="Control plane"
          value={statusLabel(overview.control_plane.status)}
          detail={`Observed ${new Date(overview.observed_at).toLocaleTimeString()}`}
          tone="green"
        />
        <MetricCard
          label="Visible tenants"
          value={String(overview.tenants.visible)}
          detail="Within your assigned scope"
          tone="blue"
        />
        <MetricCard
          label="Recent failures"
          value={String(overview.recent_failures.length)}
          detail="No active incidents reported"
          tone={overview.recent_failures.length === 0 ? "green" : "amber"}
        />
      </section>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Tenant activity</span>
            <h2>Recently updated</h2>
          </div>
          <button className="text-button" onClick={() => navigate("/console/tenants")}>
            View all
          </button>
        </div>
        {tenants.length === 0 ? (
          <EmptyState
            title="No tenants in scope"
            message="A platform administrator can create the first tenant."
          />
        ) : (
          <TenantTable tenants={tenants.slice(0, 5)} />
        )}
      </section>
    </>
  );
}

function TenantsPage({
  tenants,
  selectedId,
  detail,
  detailError,
  canCreate,
  canUpdate,
  showCreate,
  creating,
  mutating,
  onShowCreate,
  onCreate,
  onToggleStatus,
}: {
  tenants: Tenant[];
  selectedId: string | null;
  detail: TenantDetail | null;
  detailError: string | null;
  canCreate: boolean;
  canUpdate: boolean;
  showCreate: boolean;
  creating: boolean;
  mutating: boolean;
  onShowCreate: (visible: boolean) => void;
  onCreate: (event: FormEvent<HTMLFormElement>) => void;
  onToggleStatus: () => void;
}) {
  return (
    <>
      <PageHeader
        eyebrow="Access boundaries"
        title="Tenants"
        description="Manage organization boundaries and their Scholar routing scope."
        action={
          canCreate
            ? { label: "New tenant", onClick: () => onShowCreate(true) }
            : undefined
        }
      />
      {detailError ? <InlineAlert message={detailError} /> : null}
      <div className={selectedId ? "split-layout" : undefined}>
        <section className="panel table-panel">
          {tenants.length === 0 ? (
            <EmptyState
              title="No tenants available"
              message={
                canCreate
                  ? "Create the first tenant to establish a policy and corpus boundary."
                  : "No tenants are assigned to this session."
              }
            />
          ) : (
            <TenantTable tenants={tenants} selectedId={selectedId} />
          )}
        </section>
        {selectedId ? (
          <aside className="detail-panel">
            <button
              className="close-button"
              aria-label="Close tenant details"
              onClick={() => navigate("/console/tenants")}
            >
              ×
            </button>
            {!detail && !detailError ? (
              <div className="detail-loading">Loading tenant…</div>
            ) : detail ? (
              <>
                <span className="eyebrow">Tenant detail</span>
                <h2>{detail.tenant.name}</h2>
                <StatusPill status={detail.tenant.status} />
                <dl>
                  <div>
                    <dt>Slug</dt>
                    <dd>{detail.tenant.slug}</dd>
                  </div>
                  <div>
                    <dt>Resource ID</dt>
                    <dd className="mono">{detail.tenant.id}</dd>
                  </div>
                  <div>
                    <dt>Version</dt>
                    <dd>{detail.tenant.version}</dd>
                  </div>
                  <div>
                    <dt>Last updated</dt>
                    <dd>{new Date(detail.tenant.updated_at).toLocaleString()}</dd>
                  </div>
                </dl>
                {canUpdate ? (
                  <button
                    className={
                      detail.tenant.status === "active"
                        ? "danger-button"
                        : "primary-button"
                    }
                    disabled={mutating}
                    onClick={onToggleStatus}
                  >
                    {mutating
                      ? "Applying…"
                      : detail.tenant.status === "active"
                        ? "Disable tenant"
                        : "Enable tenant"}
                  </button>
                ) : null}
              </>
            ) : null}
          </aside>
        ) : null}
      </div>
      {showCreate ? (
        <div className="modal-backdrop" role="presentation">
          <section className="modal" role="dialog" aria-modal="true">
            <button
              className="close-button"
              aria-label="Close"
              onClick={() => onShowCreate(false)}
            >
              ×
            </button>
            <span className="eyebrow">New access boundary</span>
            <h2>Create tenant</h2>
            <p>Tenant slugs are stable identifiers and cannot be changed.</p>
            <form onSubmit={onCreate}>
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
              <div className="modal-actions">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => onShowCreate(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="primary-button" disabled={creating}>
                  {creating ? "Creating…" : "Create tenant"}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </>
  );
}

function TenantTable({
  tenants,
  selectedId = null,
}: {
  tenants: Tenant[];
  selectedId?: string | null;
}) {
  return (
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
              className={tenant.id === selectedId ? "selected" : undefined}
              onClick={() =>
                navigate(`/console/tenants/${encodeURIComponent(tenant.id)}`)
              }
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
  );
}

function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <header className="page-header">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action ? (
        <button className="primary-button" onClick={action.onClick}>
          {action.label}
        </button>
      ) : null}
    </header>
  );
}

function MetricCard({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone: "green" | "blue" | "amber";
}) {
  return (
    <article className="metric-card">
      <div className={`metric-dot ${tone}`} />
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function StatusPill({ status }: { status: string }) {
  return (
    <span className={status === "active" ? "status active" : "status disabled"}>
      <i />
      {statusLabel(status)}
    </span>
  );
}

function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">◇</div>
      <h3>{title}</h3>
      <p>{message}</p>
    </div>
  );
}

function InlineAlert({ message }: { message: string }) {
  return <div className="inline-alert">{message}</div>;
}

function CenteredState({
  title,
  message,
  requestId,
  pulse = false,
  action,
}: {
  title: string;
  message?: string;
  requestId?: string | null;
  pulse?: boolean;
  action?: { label: string; href?: string; onClick?: () => void };
}) {
  return (
    <main className="centered-state">
      <div className={pulse ? "state-mark pulse" : "state-mark"}>S</div>
      <span className="eyebrow">Scholar Proxy Hub</span>
      <h1>{title}</h1>
      {message ? <p>{message}</p> : null}
      {requestId ? <code>Request {requestId}</code> : null}
      {action?.href ? (
        <a className="primary-button" href={action.href}>
          {action.label}
        </a>
      ) : action?.onClick ? (
        <button className="primary-button" onClick={action.onClick}>
          {action.label}
        </button>
      ) : null}
    </main>
  );
}
