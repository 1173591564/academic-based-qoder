import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { QualityRadarData } from "../types";

export function QualityRadar({ data }: { data: QualityRadarData }) {
  if (data.error) {
    return (
      <div className="preview-error">
        <p>{data.error}</p>
      </div>
    );
  }

  if (!data.dimensions || data.dimensions.length === 0) {
    return (
      <div className="preview-empty">
        <p>No quality data available.</p>
      </div>
    );
  }

  const chartData = data.dimensions.map((d) => ({
    name: d.name,
    score: d.score,
    max: d.max,
  }));

  const gradeColor =
    data.grade === "A"
      ? "#4caf50"
      : data.grade === "B"
      ? "#2196f3"
      : data.grade === "C"
      ? "#ff9800"
      : "#f44336";

  return (
    <div className="quality-radar">
      <div className="radar-header">
        <div className="grade-badge" style={{ backgroundColor: gradeColor }}>
          {data.grade || "N/A"}
        </div>
        <div className="total-score">
          Total: <strong>{data.total}</strong>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={400}>
        <RadarChart data={chartData}>
          <PolarGrid stroke="#444" />
          <PolarAngleAxis
            dataKey="name"
            tick={{ fill: "#ccc", fontSize: 12 }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 10]}
            tick={{ fill: "#666", fontSize: 10 }}
          />
          <Radar
            name="Score"
            dataKey="score"
            stroke="#4a9eff"
            fill="#4a9eff"
            fillOpacity={0.4}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1e1e2e",
              border: "1px solid #444",
              borderRadius: "8px",
            }}
            formatter={(value, _name, props) => {
              const payload = (props as { payload?: { max?: number; name?: string } })?.payload;
              return [`${value} / ${payload?.max || 10}`, payload?.name || ""];
            }}
          />
        </RadarChart>
      </ResponsiveContainer>

      <div className="dimension-details">
        {data.dimensions.map((d) => (
          <div key={d.key} className="dim-detail">
            <span className="dim-name">{d.name}</span>
            <div className="dim-bar">
              <div
                className="dim-fill"
                style={{
                  width: `${(d.score / d.max) * 100}%`,
                  backgroundColor: d.score / d.max >= 0.7 ? "#4caf50" : d.score / d.max >= 0.5 ? "#ff9800" : "#f44336",
                }}
              />
            </div>
            <span className="dim-score">
              {d.score}/{d.max}
            </span>
            {d.detail && <span className="dim-detail-text">{d.detail}</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
