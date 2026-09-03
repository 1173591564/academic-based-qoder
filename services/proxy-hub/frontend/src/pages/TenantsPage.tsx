import { useCallback, useEffect, useMemo, useState } from "react";

import { api, ApiError } from "../api";
import {
  activateOnKeyDown,
  EmptyState,
  InlineAlert,
  ListToolbar,
  Modal,
  PageHeader,
  ServerNotice,
  StatusPill,
  SubmitActions,
  navigate,
} from "../components";
import { useI18n } from "../i18n";
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
  const [errorRequestId, setErrorRequestId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [busy, setBusy] = useState(false);
  const { t } = useI18n();

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
    setErrorRequestId(null);
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
      setErrorRequestId(
        loadError instanceof ApiError ? loadError.requestId : null,
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
    setErrorRequestId(null);
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
      setErrorRequestId(
        mutationError instanceof ApiError ? mutationError.requestId : null,
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
    setErrorRequestId(null);
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
      setErrorRequestId(
        mutationError instanceof ApiError ? mutationError.requestId : null,
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
        eyebrow={t("ACCESS BOUNDARIES")}
        title={detail ? detail.data.name : t("Tenants")}
        description={
          detail
            ? t("Manage this tenant's identity, policy, quota, and Scholar routing boundaries.")
            : t("Manage organization boundaries and their Scholar routing scope.")
        }
        action={
          !route.tenantId && canCreate
            ? { label: t("New tenant"), onClick: () => setShowCreate(true) }
            : undefined
        }
      />
      {notice ? (
        <ServerNotice message={notice} onClose={() => setNotice(null)} />
      ) : null}
      {error ? (
        <InlineAlert message={error} requestId={errorRequestId} />
      ) : null}
      {!route.tenantId ? (
        <TenantList
          tenants={tenants}
          canCreate={canCreate}
          onCreate={() => setShowCreate(true)}
        />
      ) : !detail ? (
        error ? null : <section className="panel detail-loading">{t("Loading tenant…")}</section>
      ) : (
        <>
          <div className="subnav" aria-label={t("Tenant sections")}>
            <button
              type="button"
              className={route.section === "summary" ? "active" : undefined}
              onClick={() => navigate(tenantPath(detail.data.id, "summary"))}
            >
              {t("Summary")}
            </button>
            {canManageAccess ? (
              <button
                type="button"
                className={route.section === "access" ? "active" : undefined}
                onClick={() => navigate(tenantPath(detail.data.id, "access"))}
              >
                {t("Teams & memberships")}
              </button>
            ) : null}
            {canViewPolicies ? (
              <button
                type="button"
                className={route.section === "policies" ? "active" : undefined}
                onClick={() => navigate(tenantPath(detail.data.id, "policies"))}
              >
                {t("Policy, quota & route")}
              </button>
            ) : null}
            <button
              type="button"
              className="back-link"
              onClick={() => navigate("/console/tenants")}
            >
              {t("All tenants")}
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
          title={t("Create tenant")}
          description={t("Tenant slugs are stable identifiers and cannot be changed.")}
          onClose={() => setShowCreate(false)}
        >
          <form onSubmit={(event) => void createTenant(event)}>
            <label>
              {t("Display name")}
              <input name="name" required maxLength={200} autoFocus />
            </label>
            <label>
              {t("Slug")}
              <input
                name="slug"
                required
                minLength={3}
                maxLength={64}
                pattern="[a-z0-9][a-z0-9-]+[a-z0-9]"
                autoCapitalize="none"
                autoComplete="off"
                spellCheck={false}
                title={t(
                  "Use 3–64 lowercase letters, numbers, or hyphens; start and end with a letter or number.",
                )}
                placeholder="research-platform"
              />
            </label>
            <SubmitActions
              busy={busy}
              submitLabel={t("Create tenant")}
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
  onCreate,
}: {
  tenants: Tenant[];
  canCreate: boolean;
  onCreate: () => void;
}) {
  const { t } = useI18n();
  const [search, setSearch] = useState("");
  const filteredTenants = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    if (!query) {
      return tenants;
    }
    return tenants.filter((tenant) =>
      [tenant.name, tenant.slug, tenant.status].some((value) =>
        value.toLocaleLowerCase().includes(query),
      ),
    );
  }, [search, tenants]);

  if (tenants.length === 0) {
    return (
      <section className="panel">
        <EmptyState
          title={t("No tenants available")}
          message={
            canCreate
              ? t("Create the first tenant to establish a policy and corpus boundary.")
              : t("No tenants are assigned to this session.")
          }
          action={
            canCreate
              ? { label: t("Create tenant"), onClick: onCreate }
              : undefined
          }
        />
      </section>
    );
  }
  return (
    <section className="panel">
      <ListToolbar
        value={search}
        onChange={setSearch}
        label={t("Search tenants")}
        placeholder={t("Search by name, slug, or status")}
        resultCount={filteredTenants.length}
        totalCount={tenants.length}
      />
      {filteredTenants.length === 0 ? (
        <EmptyState
          title={t("No matching tenants")}
          message={t("Try a different name, slug, or status.")}
          action={{ label: t("Clear search"), onClick: () => setSearch("") }}
        />
      ) : (
        <div className="table-wrap">
          <table className="responsive-table">
            <thead>
              <tr>
                <th>{t("Tenant")}</th>
                <th>{t("Status")}</th>
                <th>{t("Version")}</th>
                <th>{t("Updated")}</th>
                <th aria-label={t("Open")} />
              </tr>
            </thead>
            <tbody>
              {filteredTenants.map((tenant) => (
                <tr
                  key={tenant.id}
                  className="interactive-row"
                  tabIndex={0}
                  aria-label={`${t("Open tenant")} ${tenant.name}`}
                  onClick={() => navigate(tenantPath(tenant.id, "summary"))}
                  onKeyDown={(event) =>
                    activateOnKeyDown(event, () =>
                      navigate(tenantPath(tenant.id, "summary")),
                    )
                  }
                >
                  <td data-label={t("Tenant")}>
                    <strong>{tenant.name}</strong>
                    <span>{tenant.slug}</span>
                  </td>
                  <td data-label={t("Status")}>
                    <StatusPill status={tenant.status} />
                  </td>
                  <td className="mono" data-label={t("Version")}>
                    v{tenant.version}
                  </td>
                  <td data-label={t("Updated")}>
                    {new Date(tenant.updated_at).toLocaleDateString()}
                  </td>
                  <td className="row-arrow" aria-hidden="true">
                    ›
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
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
  const { t } = useI18n();
  return (
    <div className="summary-grid">
      <section className="panel summary-card">
        <span className="eyebrow">{t("Tenant identity")}</span>
        <div className="summary-title">
          <h2>{tenant.name}</h2>
          <StatusPill status={tenant.status} />
        </div>
        <dl>
          <div>
            <dt>{t("Slug")}</dt>
            <dd>{tenant.slug}</dd>
          </div>
          <div>
            <dt>{t("Resource ID")}</dt>
            <dd className="mono">{tenant.id}</dd>
          </div>
          <div>
            <dt>{t("Version")}</dt>
            <dd>{tenant.version}</dd>
          </div>
          <div>
            <dt>{t("Last updated")}</dt>
            <dd>{new Date(tenant.updated_at).toLocaleString()}</dd>
          </div>
        </dl>
        {canUpdate ? (
          <button
            type="button"
            className={
              tenant.status === "active" ? "danger-button" : "primary-button"
            }
            disabled={busy}
            aria-busy={busy}
            onClick={onToggle}
          >
            {tenant.status === "active" ? t("Disable tenant") : t("Enable tenant")}
          </button>
        ) : null}
      </section>
      <section className="panel summary-card">
        <span className="eyebrow">{t("Security boundary")}</span>
        <h2>{t("Fail-closed administration")}</h2>
        <p>
          {t(
            "Browser capabilities control presentation only. The Proxy Hub API independently enforces role, tenant scope, CSRF, ETag, and idempotency requirements on every mutation.",
          )}
        </p>
      </section>
    </div>
  );
}
