import { useCallback, useEffect, useState } from "react";

import { api, ApiError, type ApiResult } from "../api";
import {
  InlineAlert,
  PanelState,
  ServerNotice,
  StatusPill,
} from "../components";
import { useI18n } from "../i18n";
import { loadFailure, type LoadFailure } from "../load";
import type {
  AdminMe,
  ListResponse,
  QuotaPolicy,
  ResourceState,
  ScholarBackend,
  TenantRoute,
  ToolPolicy,
} from "../types";

export const SCHOLAR_TOOLS = [
  "scholar_search",
  "scholar_vec_search",
  "scholar_info",
  "scholar_section",
  "scholar_passages",
  "scholar_cite_network",
  "scholar_graph_query",
  "scholar_lineage",
  "scholar_graph_stats",
  "scholar_list_papers",
  "scholar_arxiv_search",
  "read_parsed_paper",
  "scholar_read_output_file",
  "read_skill",
  "scholar_auto_notes",
  "scholar_interests",
] as const;

interface PolicyData {
  toolPolicy: ResourceState<ToolPolicy | null>;
  quotaPolicy: ResourceState<QuotaPolicy | null>;
  route: ResourceState<TenantRoute | null>;
  backends: ScholarBackend[];
}

type PolicyLoad =
  | { kind: "loading" }
  | { kind: "ready"; data: PolicyData }
  | LoadFailure;

type PolicySection = "tools" | "quota" | "route";

const CLEAN_SECTIONS: Record<PolicySection, boolean> = {
  tools: false,
  quota: false,
  route: false,
};

async function optionalResource<T>(path: string): Promise<ResourceState<T | null>> {
  try {
    const result = await api.get<T>(path);
    if (!result.etag) {
      throw new Error("The resource response did not include an ETag.");
    }
    return { data: result.data, etag: result.etag };
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return { data: null, etag: "*" };
    }
    throw error;
  }
}

function serverVersion<T extends { version: number }>(
  label: string,
  result: ApiResult<T>,
): string {
  return `Server saved ${label} version ${result.data.version} and returned ETag ${result.etag ?? "missing"}.`;
}

export function TenantPolicies({
  tenantId,
  me,
}: {
  tenantId: string;
  me: AdminMe;
}) {
  const [state, setState] = useState<PolicyLoad>({ kind: "loading" });
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorRequestId, setErrorRequestId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [dirtySections, setDirtySections] = useState(CLEAN_SECTIONS);
  const { t } = useI18n();

  const canManagePolicy = me.capabilities.includes("policy:manage");
  const canManageQuota = me.capabilities.includes("quota:manage");
  const canManageRoute = me.capabilities.includes("route:manage");
  const canReadBackends = me.capabilities.includes("backend:read");

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const prefix = `/v1/admin/tenants/${encodeURIComponent(tenantId)}`;
      const [toolPolicy, quotaPolicy, route, backends] = await Promise.all([
        optionalResource<ToolPolicy>(`${prefix}/tool-policy`),
        optionalResource<QuotaPolicy>(`${prefix}/quota-policy`),
        optionalResource<TenantRoute>(`${prefix}/backend-route`),
        canReadBackends
          ? api.get<ListResponse<ScholarBackend>>("/v1/admin/backends")
          : Promise.resolve({ data: { items: [] }, etag: null }),
      ]);
      setState({
        kind: "ready",
        data: {
          toolPolicy,
          quotaPolicy,
          route,
          backends: backends.data.items,
        },
      });
    } catch (loadError) {
      setState(loadFailure(loadError));
    }
  }, [canReadBackends, tenantId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    setDirtySections(CLEAN_SECTIONS);
  }, [tenantId]);

  const hasUnsavedChanges = Object.values(dirtySections).some(Boolean);

  useEffect(() => {
    if (!hasUnsavedChanges) {
      return;
    }
    const warnBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    const warnBeforeNavigation = (event: Event) => {
      if (!window.confirm(t("Discard unsaved changes?"))) {
        event.preventDefault();
      }
    };
    window.addEventListener("beforeunload", warnBeforeUnload);
    window.addEventListener(
      "proxy-hub:before-navigate",
      warnBeforeNavigation,
    );
    return () => {
      window.removeEventListener("beforeunload", warnBeforeUnload);
      window.removeEventListener(
        "proxy-hub:before-navigate",
        warnBeforeNavigation,
      );
    };
  }, [hasUnsavedChanges, t]);

  function markDirty(section: PolicySection): void {
    setDirtySections((current) => ({ ...current, [section]: true }));
  }

  function clearDirty(section: PolicySection): void {
    setDirtySections((current) => ({ ...current, [section]: false }));
  }

  function syncRouteCorpus(
    event: React.ChangeEvent<HTMLSelectElement>,
  ): void {
    if (state.kind !== "ready") {
      return;
    }
    const backend = state.data.backends.find(
      (candidate) => candidate.id === event.currentTarget.value,
    );
    const corpusInput = event.currentTarget.form?.elements.namedItem(
      "corpus_version",
    );
    if (backend && corpusInput instanceof HTMLInputElement) {
      corpusInput.value = backend.corpus_version;
    }
  }

  async function reloadToolPolicy(): Promise<void> {
    const toolPolicy = await optionalResource<ToolPolicy>(
      `/v1/admin/tenants/${encodeURIComponent(tenantId)}/tool-policy`,
    );
    setState((current) =>
      current.kind === "ready"
        ? {
            kind: "ready",
            data: { ...current.data, toolPolicy },
          }
        : current,
    );
  }

  async function reloadQuotaPolicy(): Promise<void> {
    const quotaPolicy = await optionalResource<QuotaPolicy>(
      `/v1/admin/tenants/${encodeURIComponent(tenantId)}/quota-policy`,
    );
    setState((current) =>
      current.kind === "ready"
        ? {
            kind: "ready",
            data: { ...current.data, quotaPolicy },
          }
        : current,
    );
  }

  async function reloadRoute(): Promise<void> {
    const route = await optionalResource<TenantRoute>(
      `/v1/admin/tenants/${encodeURIComponent(tenantId)}/backend-route`,
    );
    setState((current) =>
      current.kind === "ready"
        ? {
            kind: "ready",
            data: { ...current.data, route },
          }
        : current,
    );
  }

  async function saveToolPolicy(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state.kind !== "ready") {
      return;
    }
    const form = new FormData(event.currentTarget);
    const allowedTools = SCHOLAR_TOOLS.filter((tool) => form.has(tool));
    if (
      !window.confirm(
        `Apply an exact allowlist containing ${allowedTools.length} Scholar tools?`,
      )
    ) {
      return;
    }
    setBusy("tools");
    setError(null);
    setErrorRequestId(null);
    try {
      const result = await api.put<ToolPolicy>(
        `/v1/admin/tenants/${encodeURIComponent(tenantId)}/tool-policy`,
        { allowed_tools: allowedTools },
        state.data.toolPolicy.etag,
      );
      setNotice(serverVersion("tool policy", result));
      clearDirty("tools");
      setState((current) =>
        current.kind === "ready"
          ? {
              kind: "ready",
              data: {
                ...current.data,
                toolPolicy: {
                  data: result.data,
                  etag: result.etag ?? current.data.toolPolicy.etag,
                },
              },
            }
          : current,
      );
    } catch (mutationError) {
      setError(
        mutationError instanceof ApiError
          ? mutationError.message
          : "Tool policy update failed.",
      );
      setErrorRequestId(
        mutationError instanceof ApiError ? mutationError.requestId : null,
      );
      if (mutationError instanceof ApiError && mutationError.status === 412) {
        clearDirty("tools");
        await reloadToolPolicy();
      }
    } finally {
      setBusy(null);
    }
  }

  async function saveQuotaPolicy(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state.kind !== "ready") {
      return;
    }
    const form = new FormData(event.currentTarget);
    setBusy("quota");
    setError(null);
    setErrorRequestId(null);
    try {
      const result = await api.put<QuotaPolicy>(
        `/v1/admin/tenants/${encodeURIComponent(tenantId)}/quota-policy`,
        {
          quota_class: String(form.get("quota_class") ?? "").trim(),
          request_limit: Number(form.get("request_limit")),
          period_seconds: Number(form.get("period_seconds")),
          concurrency_limit: Number(form.get("concurrency_limit")),
          enforcement_enabled: form.has("enforcement_enabled"),
        },
        state.data.quotaPolicy.etag,
      );
      setNotice(serverVersion("quota policy", result));
      clearDirty("quota");
      setState((current) =>
        current.kind === "ready"
          ? {
              kind: "ready",
              data: {
                ...current.data,
                quotaPolicy: {
                  data: result.data,
                  etag: result.etag ?? current.data.quotaPolicy.etag,
                },
              },
            }
          : current,
      );
    } catch (mutationError) {
      setError(
        mutationError instanceof ApiError
          ? mutationError.message
          : "Quota policy update failed.",
      );
      setErrorRequestId(
        mutationError instanceof ApiError ? mutationError.requestId : null,
      );
      if (mutationError instanceof ApiError && mutationError.status === 412) {
        clearDirty("quota");
        await reloadQuotaPolicy();
      }
    } finally {
      setBusy(null);
    }
  }

  async function saveRoute(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state.kind !== "ready") {
      return;
    }
    const form = new FormData(event.currentTarget);
    const status = String(form.get("status"));
    if (
      status === "active" &&
      !window.confirm(
        "Activate this tenant route? The server will require a current successful backend probe.",
      )
    ) {
      return;
    }
    setBusy("route");
    setError(null);
    setErrorRequestId(null);
    try {
      const result = await api.put<TenantRoute>(
        `/v1/admin/tenants/${encodeURIComponent(tenantId)}/backend-route`,
        {
          backend_id: String(form.get("backend_id")),
          corpus_version: String(form.get("corpus_version")).trim(),
          status,
        },
        state.data.route.etag,
      );
      setNotice(serverVersion("backend route", result));
      clearDirty("route");
      setState((current) =>
        current.kind === "ready"
          ? {
              kind: "ready",
              data: {
                ...current.data,
                route: {
                  data: result.data,
                  etag: result.etag ?? current.data.route.etag,
                },
              },
            }
          : current,
      );
    } catch (mutationError) {
      setError(
        mutationError instanceof ApiError
          ? mutationError.message
          : "Backend route update failed.",
      );
      setErrorRequestId(
        mutationError instanceof ApiError ? mutationError.requestId : null,
      );
      if (mutationError instanceof ApiError && mutationError.status === 412) {
        clearDirty("route");
        await reloadRoute();
      }
    } finally {
      setBusy(null);
    }
  }

  if (state.kind === "loading") {
    return (
      <section className="panel">
        <PanelState kind="loading" />
      </section>
    );
  }
  if (state.kind === "denied" || state.kind === "unavailable") {
    return (
      <section className="panel">
        <PanelState
          kind={state.kind}
          message={state.message}
          requestId={state.requestId}
          onRetry={() => void load()}
        />
      </section>
    );
  }

  const toolPolicy = state.data.toolPolicy.data;
  const quotaPolicy = state.data.quotaPolicy.data;
  const route = state.data.route.data;

  return (
    <>
      {notice ? (
        <ServerNotice message={notice} onClose={() => setNotice(null)} />
      ) : null}
      {error ? (
        <InlineAlert message={error} requestId={errorRequestId} />
      ) : null}
      {hasUnsavedChanges ? (
        <div className="unsaved-banner" role="status" aria-live="polite">
          {t("You have unsaved changes.")}
        </div>
      ) : null}
      <div className="settings-grid">
        <section className="panel settings-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">{t("Deny by default")}</span>
              <h2>{t("Tool policy")}</h2>
            </div>
            <div className="panel-actions">
              {dirtySections.tools ? (
                <span className="unsaved-badge">{t("Unsaved")}</span>
              ) : null}
              {toolPolicy ? <span className="mono">v{toolPolicy.version}</span> : null}
            </div>
          </div>
          <form
            key={toolPolicy?.version ?? "new-tool-policy"}
            className="settings-form"
            onChange={() => markDirty("tools")}
            onSubmit={(event) => void saveToolPolicy(event)}
          >
            <div className="tool-grid">
              {SCHOLAR_TOOLS.map((tool) => (
                <label className="check-row" key={tool}>
                  <input
                    type="checkbox"
                    name={tool}
                    defaultChecked={toolPolicy?.allowed_tools.includes(tool) ?? false}
                    disabled={!canManagePolicy}
                  />
                  <span title={tool}>{tool}</span>
                </label>
              ))}
            </div>
            {canManagePolicy ? (
              <button
                className="primary-button"
                type="submit"
                disabled={busy === "tools"}
                aria-busy={busy === "tools"}
              >
                {busy === "tools" ? t("Saving…") : t("Save exact allowlist")}
              </button>
            ) : null}
          </form>
        </section>
        <div className="settings-column">
          <section className="panel settings-panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">{t("Request enforcement")}</span>
                <h2>{t("Quota policy")}</h2>
              </div>
              <div className="panel-actions">
                {dirtySections.quota ? (
                  <span className="unsaved-badge">{t("Unsaved")}</span>
                ) : null}
                {quotaPolicy ? (
                  <StatusPill
                    status={
                      quotaPolicy.enforcement_enabled ? "active" : "disabled"
                    }
                  />
                ) : null}
              </div>
            </div>
            <form
              key={quotaPolicy?.version ?? "new-quota-policy"}
              className="settings-form"
              onChange={() => markDirty("quota")}
              onSubmit={(event) => void saveQuotaPolicy(event)}
            >
              <label>
                {t("Quota class")}
                <input
                  name="quota_class"
                  required
                  maxLength={64}
                  autoComplete="off"
                  defaultValue={quotaPolicy?.quota_class ?? "standard"}
                  disabled={!canManageQuota}
                />
              </label>
              <div className="field-grid">
                <label>
                  {t("Request limit")}
                  <input
                    name="request_limit"
                    type="number"
                    min={1}
                    step={1}
                    required
                    defaultValue={quotaPolicy?.request_limit ?? 1000}
                    disabled={!canManageQuota}
                  />
                </label>
                <label>
                  {t("Period seconds")}
                  <input
                    name="period_seconds"
                    type="number"
                    min={1}
                    step={1}
                    required
                    defaultValue={quotaPolicy?.period_seconds ?? 3600}
                    disabled={!canManageQuota}
                  />
                </label>
                <label>
                  {t("Concurrency limit")}
                  <input
                    name="concurrency_limit"
                    type="number"
                    min={1}
                    step={1}
                    required
                    defaultValue={quotaPolicy?.concurrency_limit ?? 5}
                    disabled={!canManageQuota}
                  />
                </label>
              </div>
              <label className="check-row">
                <input
                  type="checkbox"
                  name="enforcement_enabled"
                  defaultChecked={quotaPolicy?.enforcement_enabled ?? true}
                  disabled={!canManageQuota}
                />
                <span>{t("Enforce request and concurrency limits")}</span>
              </label>
              {canManageQuota ? (
                <button
                  className="primary-button"
                  type="submit"
                  disabled={busy === "quota"}
                  aria-busy={busy === "quota"}
                >
                  {busy === "quota" ? t("Saving…") : t("Save quota")}
                </button>
              ) : null}
            </form>
          </section>
          <section className="panel settings-panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">{t("Explicit affinity")}</span>
                <h2>{t("Backend route")}</h2>
              </div>
              <div className="panel-actions">
                {dirtySections.route ? (
                  <span className="unsaved-badge">{t("Unsaved")}</span>
                ) : null}
                {route ? <StatusPill status={route.status} /> : null}
              </div>
            </div>
            {canManageRoute ? (
              <form
                key={route?.version ?? "new-route"}
                className="settings-form"
                onChange={() => markDirty("route")}
                onSubmit={(event) => void saveRoute(event)}
              >
                <label>
                  {t("Scholar backend")}
                  <select
                    name="backend_id"
                    required
                    defaultValue={route?.backend_id ?? ""}
                    onChange={syncRouteCorpus}
                  >
                    <option value="" disabled>
                      {t("Select backend")}
                    </option>
                    {state.data.backends.map((backend) => (
                      <option key={backend.id} value={backend.id}>
                        {backend.name} · {backend.corpus_version}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  {t("Corpus version")}
                  <input
                    name="corpus_version"
                    required
                    maxLength={128}
                    defaultValue={route?.corpus_version ?? ""}
                  />
                </label>
                <label>
                  {t("Route status")}
                  <select name="status" defaultValue={route?.status ?? "disabled"}>
                    <option value="disabled">{t("Disabled")}</option>
                    <option value="active">{t("Operational")}</option>
                  </select>
                </label>
                <button
                  className="primary-button"
                  type="submit"
                  disabled={busy === "route"}
                  aria-busy={busy === "route"}
                >
                  {busy === "route" ? t("Saving…") : t("Save route")}
                </button>
              </form>
            ) : route ? (
              <dl className="compact-definition">
                <div>
                  <dt>{t("Backend")}</dt>
                  <dd>{route.backend_id}</dd>
                </div>
                <div>
                  <dt>{t("Corpus")}</dt>
                  <dd>{route.corpus_version}</dd>
                </div>
              </dl>
            ) : (
              <div className="panel-state">{t("No explicit route is configured.")}</div>
            )}
          </section>
        </div>
      </div>
    </>
  );
}
