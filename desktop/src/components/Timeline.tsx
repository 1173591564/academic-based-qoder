import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { TimelineData } from "../types";

export function Timeline({ data }: { data: TimelineData }) {
  if (data.error) {
    return (
      <div className="preview-error">
        <p>{data.error}</p>
      </div>
    );
  }

  if (!data.years || data.years.length === 0) {
    return (
      <div className="preview-empty">
        <p>No timeline data available.</p>
      </div>
    );
  }

  const chartData = data.years.map((y: { year: number; count: number; papers: { id: string; title: string }[] }) => ({
    year: String(y.year),
    count: y.count,
    papers: y.papers,
  }));

  return (
    <div className="kb-dashboard">
      <div className="metrics-header">
        <h3>Timeline: {data.topic}</h3>
        <span className="runtime-badge">{data.total} papers</span>
      </div>

      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis dataKey="year" tick={{ fill: "#ccc", fontSize: 11 }} />
          <YAxis tick={{ fill: "#ccc", fontSize: 11 }} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1e1e2e",
              border: "1px solid #444",
              borderRadius: "8px",
              maxWidth: "400px",
            }}
            formatter={(_value, _name, props) => {
              const papers = (props as { payload?: { papers?: { id: string; title: string }[] } })?.payload?.papers || [];
              if (papers.length === 0) return ["0", ""];
              const titles = papers.slice(0, 5).map((p) => p.title).join("\n");
              return [`${papers.length} papers`, titles];
            }}
          />
          <Bar dataKey="count" fill="#D4A574" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>

      <div className="chart-section">
        <h3>Key Papers by Year</h3>
        {data.years.map((y: { year: number; count: number; papers: { id: string; title: string }[] }) => (
          <div key={y.year} className="coverage-item">
            <span className="coverage-label">{y.year}</span>
            <span className="hint">
              {y.papers.slice(0, 3).map((p: { id: string; title: string }) => p.title).join("; ")}
              {y.papers.length > 3 ? ` +${y.papers.length - 3} more` : ""}
            </span>
            <span className="coverage-pct">{y.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
