import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { ExperimentMetricsData } from "../types";

export function ExperimentMetrics({ data }: { data: ExperimentMetricsData }) {
  if (data.error) {
    return (
      <div className="preview-error">
        <p>{data.error}</p>
      </div>
    );
  }

  if (!data.has_results) {
    return (
      <div className="preview-empty">
        <p>No experiment results found.</p>
        <p className="hint">
          Run: python -m scholar exp-codegen {data.paper_id} &&
          python -m scholar exp-run {data.paper_id}
        </p>
      </div>
    );
  }

  const chartData = data.comparison.map((c: { name: string; ours: number; theirs: number | null }) => ({
    name: c.name,
    Ours: c.ours,
    Paper: c.theirs,
  }));

  return (
    <div className="experiment-metrics">
      <div className="metrics-header">
        <h3>{data.paper_title}</h3>
        <div className="metrics-meta">
          {data.mode && <span className="mode-badge">Mode: {data.mode}</span>}
          {data.runtime_seconds != null && (
            <span className="runtime-badge">Runtime: {data.runtime_seconds}s</span>
          )}
        </div>
      </div>

      {chartData.length > 0 ? (
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis dataKey="name" tick={{ fill: "#ccc", fontSize: 12 }} />
            <YAxis tick={{ fill: "#ccc", fontSize: 11 }} />
            <Tooltip
              contentStyle={{
                backgroundColor: "#1e1e2e",
                border: "1px solid #444",
                borderRadius: "8px",
              }}
            />
            <Legend wrapperStyle={{ fontSize: "12px" }} />
            <Bar dataKey="Ours" fill="#4a9eff" radius={[4, 4, 0, 0]} />
            <Bar dataKey="Paper" fill="#ff6b6b" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <p className="hint">No metrics extracted from experiment output.</p>
      )}

      <div className="metrics-table">
        <h4>Extracted Metrics</h4>
        <table>
          <thead>
            <tr>
              <th>Metric</th>
              <th>Our Result</th>
              <th>Paper Reported</th>
              <th>Gap</th>
            </tr>
          </thead>
          <tbody>
            {data.comparison.map((c: { name: string; ours: number; theirs: number | null; gap: number | null }) => (
              <tr key={c.name}>
                <td>{c.name}</td>
                <td className="value-ours">{c.ours.toFixed(4)}</td>
                <td className="value-theirs">
                  {c.theirs != null ? c.theirs.toFixed(4) : "—"}
                </td>
                <td className="value-gap">
                  {c.gap != null
                    ? `${c.gap > 0 ? "+" : ""}${(c.gap * 100).toFixed(1)}%`
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
