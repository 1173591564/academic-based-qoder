import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../api";
import {
  EmptyState,
  ListToolbar,
  PageHeader,
  PanelState,
  StatusPill,
} from "../components";
import { useI18n } from "../i18n";
import { defaultTimeRange, loadFailure, queryString, type LoadFailure } from "../load";
import type { ListResponse, TokenAuditEvent } from "../types";

type AuditLoad =
  | { kind: "loading" }
  | { kind: "ready"; data: TokenAuditEvent[] }
  | LoadFailure;

export function TokenAuditPage() {
  const { t } = useI18n();
  const range = useMemo(defaultTimeRange, []);
  const [state, setState] = useState<AuditLoad>({ kind: "loading" });
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const query = queryString({
        from: range.from,
        to: range.to,
        limit: "100",
      });
      const result = await api.get<ListResponse<TokenAuditEvent>>(
        `/v1/admin/token-audit?${query}`,
      );
      setState({ kind: "ready", data: result.data.items });
    } catch (loadError) {
      setState(loadFailure(loadError));
    }
  }, [range.from, range.to]);

  useEffect(() => {
    void load();
  }, [load]);

  const filteredEvents = useMemo(() => {
    if (state.kind !== "ready") {
      return [];
    }
    const query = search.trim().toLocaleLowerCase();
    if (!query) {
      return state.data;
    }
    return state.data.filter((event) =>
      [
        event.token_name ?? "",
        event.mcp_tool ?? "",
        event.result,
        event.request_id,
      ].some((value) => value.toLocaleLowerCase().includes(query)),
    );
  }, [search, state]);

  return (
    <>
      <PageHeader
        eyebrow={t("180-DAY RETENTION")}
        title={t("Audit log")}
        description={t(
          "Token name, MCP Tool, result, latency, and Request ID. Research content is never stored.",
        )}
      />
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
        ) : state.data.length === 0 ? (
          <EmptyState
            title={t("No audit events")}
            message={t("Scholar MCP Tool calls from the last 24 hours will appear here.")}
          />
        ) : (
          <>
            <ListToolbar
              value={search}
              onChange={setSearch}
              label={t("Search audit log")}
              placeholder={t("Search by Token, MCP Tool, result, or Request ID")}
              resultCount={filteredEvents.length}
              totalCount={state.data.length}
            />
            <div className="table-wrap">
              <table className="responsive-table token-audit-table">
                <thead>
                  <tr>
                    <th>{t("Time")}</th>
                    <th>{t("Token name")}</th>
                    <th>{t("MCP Tool")}</th>
                    <th>{t("Result")}</th>
                    <th>{t("Latency")}</th>
                    <th>{t("Request ID")}</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredEvents.map((event) => (
                    <tr key={`${event.request_id}:${event.occurred_at}`}>
                      <td data-label={t("Time")}>{new Date(event.occurred_at).toLocaleString()}</td>
                      <td data-label={t("Token name")}><strong>{event.token_name ?? t("Unknown Token")}</strong></td>
                      <td className="mono" data-label={t("MCP Tool")}>{event.mcp_tool ?? "—"}</td>
                      <td data-label={t("Result")}><StatusPill status={event.result} /></td>
                      <td data-label={t("Latency")}>{event.duration_ms === null ? "—" : `${event.duration_ms} ms`}</td>
                      <td className="mono request-id" data-label={t("Request ID")}>{event.request_id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </>
  );
}
