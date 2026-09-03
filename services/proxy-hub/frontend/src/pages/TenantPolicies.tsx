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
  const [notice, setNotice] = useState<string | null>(null);
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
    try {
      const result = await api.put<ToolPolicy>(
        `/v1/admin/tenants/${encodeURIComponent(tenantId)}/tool-policy`,
        { allowed_tools: allowedTools },
        state.data.toolPolicy.etag,
      );
      setNotice(serverVersion("tool policy", result));
      await load();
    } catch (mutationError) {
      setError(
        mutationError instanceof ApiError
          ? mutationError.message
          : "Tool policy update failed.",
      );
      if (mutationError instanceof ApiError && mutationError.status === 412) {
        await load();
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
      await load();
    } catch (mutationError) {
      setError(
        mutationError instanceof ApiError
          ? mutationError.message
          : "Quota policy update failed.",
      );
      if (mutationError instanceof ApiError && mutationError.status === 412) {
        await load();
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
      await load();
    } catch (mutationError) {
      setError(
        mutationError instanceof ApiError
          ? mutationError.message
          : "Backend route update failed.",
      );
      if (mutationError instanceof ApiError && mutationError.status === 412) {
        await load();
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
      {error ? <InlineAlert message={error} /> : null}
      <div className="settings-grid">
        <section className="panel settings-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">{t("Deny by default")}</span>
              <h2>{t("Tool policy")}</h2>
            </div>
            {toolPolicy ? <span className="mono">v{toolPolicy.version}</span> : null}
          </div>
          <form className="settings-form" onSubmit={(event) => void saveToolPolicy(event)}>
            <div className="tool-grid">
              {SCHOLAR_TOOLS.map((tool) => (
                <label className="check-row" key={tool}>
                  <input
                    type="checkbox"
                    name={tool}
                    defaultChecked={toolPolicy?.allowed_tools.includes(tool) ?? false}
                    disabled={!canManagePolicy}
                  />
                  <span>{tool}</span>
                </label>
              ))}
            </div>
            {canManagePolicy ? (
              <button
                className="primary-button"
                type="submit"
                disabled={busy === "tools"}
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
              {quotaPolicy ? (
                <StatusPill
                  status={quotaPolicy.enforcement_enabled ? "active" : "disabled"}
                />
              ) : null}
            </div>
            <form className="settings-form" onSubmit={(event) => void saveQuotaPolicy(event)}>
              <label>
                {t("Quota class")}
                <input
                  name="quota_class"
                  required
                  maxLength={64}
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
              {route ? <StatusPill status={route.status} /> : null}
            </div>
            {canManageRoute ? (
              <form className="settings-form" onSubmit={(event) => void saveRoute(event)}>
                <label>
                  {t("Scholar backend")}
                  <select
                    name="backend_id"
                    required
                    defaultValue={route?.backend_id ?? ""}
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
