import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../api";
import {
  EmptyState,
  ListToolbar,
  MetricCard,
  PaginationControls,
  PageHeader,
  PanelState,
} from "../components";
import { useI18n } from "../i18n";
import {
  currentQueryValue,
  defaultTimeRange,
  loadFailure,
  queryString,
  replaceQueryValue,
  type LoadFailure,
} from "../load";
import type { AdminMe, Tenant, UsagePage as UsageResponse } from "../types";

type UsageLoad =
  | { kind: "loading" }
  | { kind: "ready"; data: UsageResponse }
  | LoadFailure;

function hasGlobalScope(me: AdminMe): boolean {
  return me.roles.some(
    (grant) =>
      grant.role === "platform_admin" ||
      (grant.role === "auditor" && grant.tenant_id === null),
  );
}

export function UsagePage({
  me,
  tenants,
}: {
  me: AdminMe;
  tenants: Tenant[];
}) {
  const range = useMemo(defaultTimeRange, []);
  const globalScope = hasGlobalScope(me);
  const { t } = useI18n();
  const [tenantId, setTenantId] = useState(() => {
    const requestedTenant = currentQueryValue("tenant");
    if (
      requestedTenant &&
      tenants.some((tenant) => tenant.id === requestedTenant)
    ) {
      return requestedTenant;
    }
    return globalScope ? "" : (tenants[0]?.id ?? "");
  });
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<(string | null)[]>([]);
  const [state, setState] = useState<UsageLoad>({ kind: "loading" });
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    if (!globalScope && !tenantId) {
      setState({
        kind: "unavailable",
        message: "No tenant is available in this usage scope.",
        requestId: null,
      });
      return;
    }
    setState({ kind: "loading" });
    try {
      const base =
        tenantId.length > 0
          ? `/v1/admin/tenants/${encodeURIComponent(tenantId)}/usage`
          : "/v1/admin/usage";
      const query = queryString({
        from: range.from,
        to: range.to,
        cursor,
        limit: "50",
      });
      const result = await api.get<UsageResponse>(`${base}?${query}`);
      setState({ kind: "ready", data: result.data });
    } catch (error) {
      setState(loadFailure(error));
    }
  }, [cursor, globalScope, range.from, range.to, tenantId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    replaceQueryValue("tenant", tenantId);
  }, [tenantId]);

  const totals =
    state.kind === "ready"
      ? state.data.items.reduce(
          (value, item) => ({
            requests: value.requests + item.requests.total,
            failures: value.failures + item.requests.failed + item.requests.rejected,
            bytes: value.bytes + item.returned_bytes,
          }),
          { requests: 0, failures: 0, bytes: 0 },
        )
      : { requests: 0, failures: 0, bytes: 0 };

  const filteredItems = useMemo(() => {
    if (state.kind !== "ready") {
      return [];
    }
    const query = search.trim().toLocaleLowerCase();
    if (!query) {
      return state.data.items;
    }
    return state.data.items.filter((item) => {
      const tenantName =
        tenants.find((tenant) => tenant.id === item.tenant_id)?.name ?? "";
      return [tenantName, item.tenant_id].some((value) =>
        value.toLocaleLowerCase().includes(query),
      );
    });
  }, [search, state, tenants]);

  function selectTenant(value: string): void {
    setTenantId(value);
    setCursor(null);
    setCursorHistory([]);
    setSearch("");
  }

  function nextPage(nextCursor: string): void {
    setCursorHistory((history) => [...history, cursor]);
    setCursor(nextCursor);
  }

  function previousPage(): void {
    const previousCursor = cursorHistory[cursorHistory.length - 1] ?? null;
    setCursorHistory((history) => history.slice(0, -1));
    setCursor(previousCursor);
  }

  return (
    <>
      <PageHeader
        eyebrow={t("Immutable reporting")}
        title={t("Usage")}
        description={t("Request outcomes, latency, returned bytes, and quota consumption for the last 24 hours. Reporting never changes quota counters.")}
      />
      <div className="filter-bar">
        <label>
          {t("Scope")}
          <select
            value={tenantId}
            onChange={(event) => selectTenant(event.target.value)}
          >
            {globalScope ? <option value="">{t("All tenants")}</option> : null}
            {tenants.map((tenant) => (
              <option key={tenant.id} value={tenant.id}>
                {tenant.name}
              </option>
            ))}
          </select>
        </label>
        <div className="range-copy">
          {new Date(range.from).toLocaleString()} –{" "}
          {new Date(range.to).toLocaleString()}
        </div>
      </div>
      {state.kind === "ready" ? (
        <section className="metric-grid">
          <MetricCard
            label={t("Requests")}
            value={String(totals.requests)}
            detail={t("Gateway calls in range")}
            tone="blue"
          />
          <MetricCard
            label={t("Failed or rejected")}
            value={String(totals.failures)}
            detail={t("Bounded result classes")}
            tone={totals.failures === 0 ? "green" : "amber"}
          />
          <MetricCard
            label={t("Returned bytes")}
            value={totals.bytes.toLocaleString()}
            detail={t("Model-visible response bytes")}
            tone="green"
          />
        </section>
      ) : null}
      <section className="panel">
        {state.kind === "loading" ? (
          <PanelState kind="loading" />
        ) : state.kind === "denied" || state.kind === "unavailable" ? (
          <PanelState
            kind={state.kind}
            message={state.message}
            requestId={state.requestId}
            onRetry={() => void load()}
          />
        ) : state.data.items.length === 0 ? (
          <EmptyState
            title={t("No usage rows")}
            message={t("No tenants are available in this reporting scope.")}
          />
        ) : (
          <>
            <ListToolbar
              value={search}
              onChange={setSearch}
              label={t("Search usage")}
              placeholder={t("Search by tenant name or ID")}
              resultCount={filteredItems.length}
              totalCount={state.data.items.length}
            />
            {filteredItems.length === 0 ? (
              <EmptyState
                title={t("No matching usage rows")}
                message={t("Try a different tenant name or ID.")}
                action={{
                  label: t("Clear search"),
                  onClick: () => setSearch(""),
                }}
              />
            ) : (
              <div className="table-wrap">
                <table className="responsive-table">
                  <thead>
                    <tr>
                      <th>{t("Tenant")}</th>
                      <th>{t("Requests")}</th>
                      <th>{t("Outcomes")}</th>
                      <th>{t("Latency")}</th>
                      <th>{t("Quota")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredItems.map((item) => (
                      <tr key={item.tenant_id}>
                        <td data-label={t("Tenant")}>
                          <strong>
                            {tenants.find(
                              (tenant) => tenant.id === item.tenant_id,
                            )?.name ?? item.tenant_id}
                          </strong>
                          <span className="mono">{item.tenant_id}</span>
                        </td>
                        <td data-label={t("Requests")}>
                          <strong>{item.requests.total}</strong>
                          <span>
                            {item.returned_bytes.toLocaleString()} {t("bytes")}
                          </span>
                        </td>
                        <td data-label={t("Outcomes")}>
                          <strong>
                            {item.requests.successful} {t("successful")}
                          </strong>
                          <span>
                            {item.requests.failed} {t("failed")} ·{" "}
                            {item.requests.rejected} {t("rejected")}
                          </span>
                        </td>
                        <td data-label={t("Latency")}>
                          <strong>
                            {item.latency.average_ms === null
                              ? t("No samples")
                              : `${item.latency.average_ms} ${t("ms average")}`}
                          </strong>
                          <span>
                            {item.latency.maximum_ms === null
                              ? "—"
                              : `${item.latency.maximum_ms} ${t("ms maximum")}`}
                          </span>
                        </td>
                        <td data-label={t("Quota")}>
                          <strong>
                            {item.quota.consumed} {t("consumed")}
                          </strong>
                          <span>
                            {item.quota.configured
                              ? `${item.quota.request_limit ?? 0} / ${item.quota.period_seconds ?? 0}s`
                              : t("Not configured")}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {cursorHistory.length > 0 || state.data.next_cursor ? (
              <PaginationControls
                page={cursorHistory.length + 1}
                hasPrevious={cursorHistory.length > 0}
                hasNext={Boolean(state.data.next_cursor)}
                onPrevious={previousPage}
                onNext={() => {
                  if (state.data.next_cursor) {
                    nextPage(state.data.next_cursor);
                  }
                }}
              />
            ) : null}
          </>
        )}
      </section>
    </>
  );
}
