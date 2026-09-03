import { useCallback, useEffect, useState } from "react";

import { api, ApiError } from "../api";
import {
  EmptyState,
  InlineAlert,
  PageHeader,
  PanelState,
  ServerNotice,
  StatusPill,
} from "../components";
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
  const [notice, setNotice] = useState<string | null>(null);

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
        eyebrow="Identity administration"
        title="Principals"
        description="Control login eligibility. Memberships and role bindings remain tenant-scoped resources."
      />
      {notice ? (
        <ServerNotice message={notice} onClose={() => setNotice(null)} />
      ) : null}
      {error ? <InlineAlert message={error} /> : null}
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
            title="No principals"
            message="Principals appear after the identity provider establishes them."
          />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Principal</th>
                  <th>Status</th>
                  <th>Issuer / subject</th>
                  <th>Version</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {state.data.map((principal) => (
                  <tr key={principal.id}>
                    <td>
                      <strong>
                        {principal.display_name ?? principal.email ?? principal.id}
                      </strong>
                      <span>{principal.email ?? principal.id}</span>
                    </td>
                    <td>
                      <StatusPill status={principal.status} />
                    </td>
                    <td>
                      <strong>{principal.issuer}</strong>
                      <span className="mono">{principal.subject}</span>
                    </td>
                    <td className="mono">v{principal.version}</td>
                    <td>
                      <button
                        className={
                          principal.status === "active"
                            ? "danger-button compact-button"
                            : "secondary-button compact-button"
                        }
                        disabled={busyId === principal.id}
                        onClick={() => void togglePrincipal(principal)}
                      >
                        {principal.status === "active" ? "Disable" : "Enable"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
