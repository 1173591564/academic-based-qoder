import { useCallback, useEffect, useMemo, useState } from "react";

import { api, ApiError } from "../api";
import {
  EmptyState,
  InlineAlert,
  ListToolbar,
  PageHeader,
  PanelState,
  ServerNotice,
  StatusPill,
} from "../components";
import { useI18n } from "../i18n";
import { loadFailure, type LoadFailure } from "../load";
import type { AdminPrincipal, ListResponse } from "../types";

type PrincipalLoad =
  | { kind: "loading" }
  | { kind: "ready"; data: AdminPrincipal[] }
  | LoadFailure;

export function PrincipalsPage() {
  const [state, setState] = useState<PrincipalLoad>({ kind: "loading" });
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorRequestId, setErrorRequestId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const { t } = useI18n();

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const result =
        await api.get<ListResponse<AdminPrincipal>>("/v1/admin/principals");
      setState({ kind: "ready", data: result.data.items });
    } catch (loadError) {
      setState(loadFailure(loadError));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filteredPrincipals = useMemo(() => {
    if (state.kind !== "ready") {
      return [];
    }
    const query = search.trim().toLocaleLowerCase();
    if (!query) {
      return state.data;
    }
    return state.data.filter((principal) =>
      [
        principal.display_name ?? "",
        principal.email ?? "",
        principal.id,
        principal.issuer,
        principal.subject,
        principal.status,
      ].some((value) => value.toLocaleLowerCase().includes(query)),
    );
  }, [search, state]);

  async function togglePrincipal(principal: AdminPrincipal) {
    const nextStatus = principal.status === "active" ? "disabled" : "active";
    if (
      !window.confirm(
        `${nextStatus === "active" ? "Enable" : "Disable"} ${principal.display_name ?? principal.email ?? principal.id}?`,
      )
    ) {
      return;
    }
    setBusyId(principal.id);
    setError(null);
    setErrorRequestId(null);
    try {
      const result = await api.patch<AdminPrincipal>(
        `/v1/admin/principals/${encodeURIComponent(principal.id)}`,
        { status: nextStatus },
        principal.etag,
      );
      setNotice(
        `Server returned ${result.data.display_name ?? result.data.email ?? result.data.id}, v${result.data.version}, ${result.data.status}.`,
      );
      await load();
    } catch (mutationError) {
      setError(
        mutationError instanceof ApiError
          ? mutationError.message
          : "Principal update failed.",
      );
      setErrorRequestId(
        mutationError instanceof ApiError ? mutationError.requestId : null,
      );
      if (mutationError instanceof ApiError && mutationError.status === 412) {
        await load();
      }
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow={t("Identity administration")}
        title={t("Principals")}
        description={t("Control login eligibility. Memberships and role bindings remain tenant-scoped resources.")}
      />
      {notice ? (
        <ServerNotice message={notice} onClose={() => setNotice(null)} />
      ) : null}
      {error ? (
        <InlineAlert message={error} requestId={errorRequestId} />
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
        ) : state.data.length === 0 ? (
          <EmptyState
            title={t("No principals")}
            message={t("Principals appear after the identity provider establishes them.")}
          />
        ) : (
          <>
            <ListToolbar
              value={search}
              onChange={setSearch}
              label={t("Search principals")}
              placeholder={t("Search by identity, issuer, or status")}
              resultCount={filteredPrincipals.length}
              totalCount={state.data.length}
            />
            {filteredPrincipals.length === 0 ? (
              <EmptyState
                title={t("No matching principals")}
                message={t("Try a different identity, issuer, or status.")}
                action={{
                  label: t("Clear search"),
                  onClick: () => setSearch(""),
                }}
              />
            ) : (
              <div className="table-wrap">
                <table className="responsive-table principal-table">
                  <thead>
                    <tr>
                      <th>{t("Principals")}</th>
                      <th>{t("Status")}</th>
                      <th>{t("Issuer / subject")}</th>
                      <th>{t("Action")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredPrincipals.map((principal) => (
                      <tr key={principal.id}>
                        <td className="cell-stack" data-label={t("Principals")}>
                          <strong>
                            {principal.display_name ??
                              principal.email ??
                              principal.id}
                          </strong>
                          <span
                            className="table-identifier"
                            title={principal.email ?? principal.id}
                          >
                            {principal.email ?? principal.id}
                          </span>
                          <span className="mono">v{principal.version}</span>
                        </td>
                        <td data-label={t("Status")}>
                          <StatusPill status={principal.status} />
                        </td>
                        <td
                          className="cell-stack"
                          data-label={t("Issuer / subject")}
                        >
                          <strong>{principal.issuer}</strong>
                          <span
                            className="mono table-identifier"
                            title={principal.subject}
                          >
                            {principal.subject}
                          </span>
                        </td>
                        <td data-label={t("Action")}>
                          <button
                            type="button"
                            className={
                              principal.status === "active"
                                ? "danger-button compact-button"
                                : "secondary-button compact-button"
                            }
                            disabled={busyId === principal.id}
                            aria-busy={busyId === principal.id}
                            onClick={() => void togglePrincipal(principal)}
                          >
                            {principal.status === "active"
                              ? t("Disable")
                              : t("Enable")}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </section>
    </>
  );
}
