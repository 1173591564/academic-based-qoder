import { useCallback, useEffect, useState } from "react";

import { api, ApiError } from "../api";
import {
  InlineAlert,
  MetricCard,
  PageHeader,
  PanelState,
  ServerNotice,
  StatusPill,
} from "../components";
import { useI18n } from "../i18n";
import { loadFailure, type LoadFailure } from "../load";
import type { ServiceStatus } from "../types";

type StatusLoad =
  | { kind: "loading" }
  | { kind: "ready"; data: ServiceStatus }
  | LoadFailure;

export function ServiceStatusPage() {
  const { t } = useI18n();
  const [state, setState] = useState<StatusLoad>({ kind: "loading" });
  const [probing, setProbing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const result = await api.get<ServiceStatus>("/v1/admin/service-status");
      setState({ kind: "ready", data: result.data });
    } catch (loadError) {
      setState(loadFailure(loadError));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function probe() {
    setProbing(true);
    setError(null);
    try {
      const result = await api.post<ServiceStatus>(
        "/v1/admin/service-status/probe",
        {},
      );
      setState({ kind: "ready", data: result.data });
      setNotice(t("Service check completed."));
    } catch (probeError) {
      setError(
        probeError instanceof ApiError
          ? probeError.message
          : t("Service check failed."),
      );
      setRequestId(
        probeError instanceof ApiError ? probeError.requestId : null,
      );
      await load();
    } finally {
      setProbing(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow={t("SCHOLAR BACKEND")}
        title={t("Service status")}
        description={t("Current Scholar availability and Corpus version.")}
        action={{
          label: probing ? t("Checking…") : t("Check again"),
          onClick: () => void probe(),
        }}
      />
      {notice ? (
        <ServerNotice message={notice} onClose={() => setNotice(null)} />
      ) : null}
      {error ? <InlineAlert message={error} requestId={requestId} /> : null}
      {state.kind === "loading" ? (
        <section className="panel"><PanelState kind="loading" /></section>
      ) : state.kind === "denied" || state.kind === "unavailable" ? (
        <section className="panel">
          <PanelState kind={state.kind} message={state.message} requestId={state.requestId} onRetry={() => void load()} />
        </section>
      ) : (
        <>
          {state.data.transport.development_http ? (
            <div className="transport-warning" role="alert">
              <strong>{t("Development HTTP is enabled.")}</strong>
              <span>{t("Tokens are transmitted in plaintext. Use only revocable test Tokens.")}</span>
            </div>
          ) : null}
          <section className="metric-grid service-metrics">
            <MetricCard
              label={t("Availability")}
              value={t(state.data.available ? "Available" : "Unavailable")}
              detail={t(state.data.available ? "Scholar requests can be routed." : "Scholar requests cannot be routed.")}
              tone={state.data.available ? "green" : "amber"}
            />
            <MetricCard
              label={t("Corpus version")}
              value={state.data.corpus_version ?? t("Not configured")}
              detail={t("Version reported by the active Scholar route")}
              tone="blue"
            />
            <MetricCard
              label={t("Last checked")}
              value={state.data.checked_at ? new Date(state.data.checked_at).toLocaleDateString() : t("Never")}
              detail={state.data.checked_at ? new Date(state.data.checked_at).toLocaleString() : t("Run a service check")}
              tone={state.data.checked_at ? "green" : "amber"}
            />
          </section>
          <section className="panel status-detail">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">{t("CURRENT STATE")}</span>
                <h2>{t("Scholar service")}</h2>
              </div>
              <StatusPill status={state.data.available ? "ready" : "failed"} />
            </div>
            <dl>
              <div><dt>{t("Availability")}</dt><dd>{t(state.data.available ? "Available" : "Unavailable")}</dd></div>
              <div><dt>{t("Corpus version")}</dt><dd>{state.data.corpus_version ?? t("Not configured")}</dd></div>
              <div><dt>{t("Last checked")}</dt><dd>{state.data.checked_at ? new Date(state.data.checked_at).toLocaleString() : t("Never")}</dd></div>
            </dl>
          </section>
        </>
      )}
    </>
  );
}
