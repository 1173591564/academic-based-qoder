import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../api";
import {
  EmptyState,
  PageHeader,
  PanelState,
  StatusPill,
} from "../components";
import {
  defaultTimeRange,
  loadFailure,
  queryString,
  type LoadFailure,
} from "../load";
import type { AdminMe, AuditPage as AuditResponse, Tenant } from "../types";

type AuditLoad =
  | { kind: "loading" }
  | { kind: "ready"; data: AuditResponse }
  | LoadFailure;

function hasGlobalScope(me: AdminMe): boolean {
  return me.roles.some(
    (grant) =>
      grant.role === "platform_admin" ||
      (grant.role === "auditor" && grant.tenant_id === null),
  );
}

export function AuditPage({
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
  const [state, setState] = useState<AuditLoad>({ kind: "loading" });

  const load = useCallback(async () => {
    if (!globalScope && !tenantId) {
      setState({
        kind: "unavailable",
        message: "No tenant is available in this audit scope.",
        requestId: null,
      });
      return;
    }
    setState({ kind: "loading" });
    try {
      const base =
        tenantId.length > 0
          ? `/v1/admin/tenants/${encodeURIComponent(tenantId)}/audit-events`
          : "/v1/admin/audit-events";
      const query = queryString({
        from: range.from,
        to: range.to,
        cursor,
        limit: "50",
      });
      const result = await api.get<AuditResponse>(`${base}?${query}`);
      setState({ kind: "ready", data: result.data });
    } catch (error) {
      setState(loadFailure(error));
    }
  }, [cursor, globalScope, range.from, range.to, tenantId]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <PageHeader
        eyebrow="Bounded observability"
        title="Audit events"
        description="Authorization and operational metadata from the last 24 hours. Research content, request bodies, digests, and credentials are never returned."
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
            title="No audit events"
            message="No bounded operational events were recorded in this scope."
          />
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Occurred</th>
                    <th>Action</th>
                    <th>Outcome</th>
                    <th>Tenant / resource</th>
                    <th>Latency</th>
                  </tr>
                </thead>
                <tbody>
                  {state.data.items.map((event) => (
                    <tr key={event.id}>
                      <td>
                        <strong>{new Date(event.occurred_at).toLocaleString()}</strong>
                        <span className="mono">{event.request_id}</span>
                      </td>
                      <td>
                        <strong>{event.action}</strong>
                        <span>
                          {event.tool_name ??
                            event.decision ??
                            event.result_class ??
                            "—"}
                        </span>
                      </td>
                      <td>
                        <StatusPill status={event.outcome} />
                      </td>
                      <td>
                        <strong>{event.tenant_id ?? "Platform"}</strong>
                        <span>{event.resource_id ?? event.backend_id ?? "—"}</span>
                      </td>
                      <td>{event.latency_ms === null ? "—" : `${event.latency_ms} ms`}</td>
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
