import {
  EmptyState,
  MetricCard,
  PageHeader,
  StatusPill,
  navigate,
  statusLabel,
} from "../components";
import type { Overview, Tenant } from "../types";

export function OverviewPage({
  overview,
  tenants,
}: {
  overview: Overview;
  tenants: Tenant[];
}) {
  return (
    <>
      <PageHeader
        eyebrow="Control plane"
        title="Operations overview"
        description="Current health, tenant footprint, and routing readiness."
      />
      <section className="metric-grid">
        <MetricCard
          label="Control plane"
          value={statusLabel(overview.control_plane.status)}
          detail={`Observed ${new Date(overview.observed_at).toLocaleTimeString()}`}
          tone="green"
        />
        <MetricCard
          label="Visible tenants"
          value={String(overview.tenants.visible)}
          detail="Within your assigned scope"
          tone="blue"
        />
        <MetricCard
          label="Recent failures"
          value={String(overview.recent_failures.length)}
          detail={
            overview.recent_failures.length === 0
              ? "No active incidents reported"
              : "Review audit decisions"
          }
          tone={overview.recent_failures.length === 0 ? "green" : "amber"}
        />
      </section>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Tenant activity</span>
            <h2>Recently updated</h2>
          </div>
          <button
            className="text-button"
            onClick={() => navigate("/console/tenants")}
          >
            View all
          </button>
        </div>
        {tenants.length === 0 ? (
          <EmptyState
            title="No tenants in scope"
            message="A platform administrator can create the first tenant."
          />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Tenant</th>
                  <th>Status</th>
                  <th>Version</th>
                  <th>Updated</th>
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
