import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import type { KBDashboardData } from "../types";

const PIE_COLORS = ["#4a9eff", "#ff6b6b", "#4caf50", "#ff9800", "#9c27b0", "#00bcd4", "#795548", "#607d8b"];

export function KBDashboard({ data }: { data: KBDashboardData }) {
  if (data.error) {
    return (
      <div className="preview-error">
        <p>{data.error}</p>
      </div>
    );
  }

  const yearData = Object.entries(data.by_year || {})
    .map(([year, count]) => ({ year, count }))
    .sort((a, b) => a.year.localeCompare(b.year));

  const venueData = Object.entries(data.by_venue || {})
    .map(([venue, count]) => ({ name: venue, value: count }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8);

  const coverageItems = [
    { label: "Year", value: data.coverage?.has_year || 0, total: data.parsed },
    { label: "Authors", value: data.coverage?.has_authors || 0, total: data.parsed },
    { label: "Abstract", value: data.coverage?.has_abstract || 0, total: data.parsed },
    { label: "Venue", value: data.coverage?.has_venue || 0, total: data.parsed },
  ];

  return (
    <div className="kb-dashboard">
      {/* Stats cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value">{data.parsed}</div>
          <div className="stat-label">Papers</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{data.sections}</div>
          <div className="stat-label">Sections</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{data.formulas}</div>
          <div className="stat-label">Formulas</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{data.citations}</div>
          <div className="stat-label">Citations</div>
        </div>
      </div>

      {/* Coverage bars */}
      <div className="coverage-section">
        <h3>Metadata Coverage</h3>
        {coverageItems.map((item) => {
          const pct = item.total > 0 ? (item.value / item.total) * 100 : 0;
          return (
            <div key={item.label} className="coverage-item">
              <span className="coverage-label">{item.label}</span>
              <div className="coverage-bar">
                <div
                  className="coverage-fill"
                  style={{
                    width: `${pct}%`,
                    backgroundColor: pct >= 80 ? "#4caf50" : pct >= 50 ? "#ff9800" : "#f44336",
                  }}
                />
              </div>
              <span className="coverage-pct">{pct.toFixed(0)}%</span>
            </div>
          );
        })}
      </div>

      {/* Year chart */}
      {yearData.length > 0 && (
        <div className="chart-section">
          <h3>Papers by Year</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={yearData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="year" tick={{ fill: "#ccc", fontSize: 11 }} />
              <YAxis tick={{ fill: "#ccc", fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1e1e2e",
                  border: "1px solid #444",
                  borderRadius: "8px",
                }}
              />
              <Bar dataKey="count" fill="#4a9eff" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Venue pie */}
      {venueData.length > 0 && (
        <div className="chart-section">
          <h3>Papers by Venue</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={venueData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={100}
                label={(entry: { name?: string }) => entry.name || ""}
                labelLine={false}
              >
                {venueData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1e1e2e",
                  border: "1px solid #444",
                  borderRadius: "8px",
                }}
              />
              <Legend wrapperStyle={{ fontSize: "11px" }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
