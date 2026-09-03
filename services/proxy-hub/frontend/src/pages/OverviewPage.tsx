import {
  EmptyState,
  MetricCard,
  PageHeader,
  StatusPill,
  navigate,
} from "../components";
import { statusLabel, useI18n } from "../i18n";
import { SetupChecklist } from "./SetupChecklist";
import type { Overview, Tenant } from "../types";

export function OverviewPage({
  overview,
  tenants,
}: {
  overview: Overview;
  tenants: Tenant[];
}) {
  const { t } = useI18n();
  return (
    <>
      <PageHeader
        eyebrow={t("CONTROL PLANE")}
        title={t("Operations overview")}
        description={t("Current health, tenant footprint, and routing readiness.")}
      />
      <SetupChecklist tenants={tenants} />
      <section className="metric-grid">
        <MetricCard
          label={t("Control plane")}
          value={statusLabel(overview.control_plane.status, t)}
          detail={`${t("Observed")} ${new Date(overview.observed_at).toLocaleTimeString()}`}
          tone="green"
        />
        <MetricCard
          label={t("Visible tenants")}
          value={String(overview.tenants.visible)}
          detail={t("Within your assigned scope")}
          tone="blue"
        />
        <MetricCard
          label={t("Recent failures")}
          value={String(overview.recent_failures.length)}
          detail={
            overview.recent_failures.length === 0
              ? t("No active incidents reported")
              : t("Review audit decisions")
          }
          tone={overview.recent_failures.length === 0 ? "green" : "amber"}
        />
      </section>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">{t("Tenant activity")}</span>
            <h2>{t("Recently updated")}</h2>
          </div>
          <button
            className="text-button"
            onClick={() => navigate("/console/guide")}
          >
            {t("Read the setup guide")}
          </button>
          <button
            className="text-button"
            onClick={() => navigate("/console/tenants")}
          >
            {t("View all")}
          </button>
        </div>
        {tenants.length === 0 ? (
          <EmptyState
            title={t("No tenants in scope")}
            message={t("A platform administrator can create the first tenant.")}
          />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t("Tenant")}</th>
                  <th>{t("Status")}</th>
                  <th>{t("Version")}</th>
                  <th>{t("Updated")}</th>
                </tr>
              </thead>
              <tbody>
                {tenants.slice(0, 5).map((tenant) => (
                  <tr
                    key={tenant.id}
                    onClick={() =>
                      navigate(
                        `/console/tenants/${encodeURIComponent(tenant.id)}`,
                      )
                    }
                  >
                    <td>
                      <strong>{tenant.name}</strong>
                      <span>{tenant.slug}</span>
                    </td>
                    <td>
                      <StatusPill status={tenant.status} />
                    </td>
                    <td className="mono">v{tenant.version}</td>
                    <td>{new Date(tenant.updated_at).toLocaleDateString()}</td>
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
