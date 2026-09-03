import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../api";
import {
  EmptyState,
  ListToolbar,
  PaginationControls,
  PageHeader,
  PanelState,
  StatusPill,
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
  const [state, setState] = useState<AuditLoad>({ kind: "loading" });
  const [search, setSearch] = useState("");

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

  useEffect(() => {
    replaceQueryValue("tenant", tenantId);
  }, [tenantId]);

  const filteredEvents = useMemo(() => {
    if (state.kind !== "ready") {
      return [];
    }
    const query = search.trim().toLocaleLowerCase();
    if (!query) {
      return state.data.items;
    }
    return state.data.items.filter((event) =>
      [
        event.action,
        event.outcome,
        event.tool_name ?? "",
        event.decision ?? "",
        event.result_class ?? "",
        event.tenant_id ?? "",
        event.resource_id ?? "",
        event.backend_id ?? "",
        event.request_id,
      ].some((value) => value.toLocaleLowerCase().includes(query)),
    );
  }, [search, state]);

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
        eyebrow={t("Bounded observability")}
        title={t("Audit events")}
        description={t("Authorization and operational metadata from the last 24 hours. Research content, request bodies, digests, and credentials are never returned.")}
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
            title={t("No audit events")}
            message={t("No bounded operational events were recorded in this scope.")}
          />
        ) : (
          <>
            <ListToolbar
              value={search}
              onChange={setSearch}
              label={t("Search audit events")}
              placeholder={t("Search actions, outcomes, or resources")}
              resultCount={filteredEvents.length}
              totalCount={state.data.items.length}
            />
            {filteredEvents.length === 0 ? (
              <EmptyState
                title={t("No matching audit events")}
                message={t("Try a different action, outcome, or resource.")}
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
                      <th>{t("Occurred")}</th>
                      <th>{t("Action")}</th>
                      <th>{t("Outcome")}</th>
                      <th>{t("Tenant / resource")}</th>
                      <th>{t("Latency")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredEvents.map((event) => (
                      <tr key={event.id}>
                        <td data-label={t("Occurred")}>
                          <strong>
                            {new Date(event.occurred_at).toLocaleString()}
                          </strong>
                          <span className="mono">{event.request_id}</span>
                        </td>
                        <td data-label={t("Action")}>
                          <strong>{event.action}</strong>
                          <span>
                            {event.tool_name ??
                              event.decision ??
                              event.result_class ??
                              "—"}
                          </span>
                        </td>
                        <td data-label={t("Outcome")}>
                          <StatusPill status={event.outcome} />
                        </td>
                        <td data-label={t("Tenant / resource")}>
                        <strong>{event.tenant_id ?? t("Platform")}</strong>
                          <span>
                            {event.resource_id ?? event.backend_id ?? "—"}
                          </span>
                        </td>
                        <td data-label={t("Latency")}>
                          {event.latency_ms === null
                            ? "—"
                            : `${event.latency_ms} ms`}
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
