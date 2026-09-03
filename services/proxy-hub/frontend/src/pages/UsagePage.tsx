import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../api";
import {
  EmptyState,
  MetricCard,
  PageHeader,
  PanelState,
} from "../components";
import {
  defaultTimeRange,
  loadFailure,
  queryString,
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
  const [tenantId, setTenantId] = useState(globalScope ? "" : (tenants[0]?.id ?? ""));
  const [cursor, setCursor] = useState<string | null>(null);
  const [state, setState] = useState<UsageLoad>({ kind: "loading" });

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

  return (
    <>
      <PageHeader
        eyebrow="Immutable reporting"
        title="Usage"
        description="Request outcomes, latency, returned bytes, and quota consumption for the last 24 hours. Reporting never changes quota counters."
      />
      <div className="filter-bar">
        <label>
          Scope
          <select
            value={tenantId}
            onChange={(event) => {
              setCursor(null);
              setTenantId(event.target.value);
            }}
          >
            {globalScope ? <option value="">All tenants</option> : null}
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
            label="Requests"
            value={String(totals.requests)}
            detail="Gateway calls in range"
            tone="blue"
          />
          <MetricCard
            label="Failed or rejected"
            value={String(totals.failures)}
            detail="Bounded result classes"
            tone={totals.failures === 0 ? "green" : "amber"}
          />
          <MetricCard
            label="Returned bytes"
            value={totals.bytes.toLocaleString()}
            detail="Model-visible response bytes"
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
            title="No usage rows"
            message="No tenants are available in this reporting scope."
          />
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Tenant</th>
                    <th>Requests</th>
                    <th>Outcomes</th>
                    <th>Latency</th>
                    <th>Quota</th>
                  </tr>
                </thead>
                <tbody>
                  {state.data.items.map((item) => (
                    <tr key={item.tenant_id}>
                      <td>
                        <strong>
                          {tenants.find((tenant) => tenant.id === item.tenant_id)
                            ?.name ?? item.tenant_id}
                        </strong>
                        <span className="mono">{item.tenant_id}</span>
                      </td>
                      <td>
                        <strong>{item.requests.total}</strong>
                        <span>{item.returned_bytes.toLocaleString()} bytes</span>
                      </td>
                      <td>
                        <strong>{item.requests.successful} successful</strong>
                        <span>
                          {item.requests.failed} failed · {item.requests.rejected}{" "}
                          rejected
                        </span>
                      </td>
                      <td>
                        <strong>
                          {item.latency.average_ms === null
                            ? "No samples"
                            : `${item.latency.average_ms} ms avg`}
                        </strong>
                        <span>
                          {item.latency.maximum_ms === null
                            ? "—"
                            : `${item.latency.maximum_ms} ms maximum`}
                        </span>
                      </td>
                      <td>
                        <strong>{item.quota.consumed} consumed</strong>
                        <span>
                          {item.quota.configured
                            ? `${item.quota.request_limit ?? 0} / ${item.quota.period_seconds ?? 0}s`
                            : "Not configured"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {state.data.next_cursor ? (
              <div className="pagination">
                <button
                  className="secondary-button"
                  onClick={() => setCursor(state.data.next_cursor)}
                >
                  Next page
                </button>
              </div>
            ) : null}
          </>
        )}
      </section>
    </>
  );
}
