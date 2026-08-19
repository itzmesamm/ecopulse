import { IconBadge } from "../ui/Pill";

export default function CarbonSummary({ summary }) {
  return (
    <div className="stat-row" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
      <div className="card stat-card">
        <div className="top">
          <IconBadge icon="leaf" tone="teal" />
        </div>
        <span className="value num teal">{(summary.carbonSavedKg / 1000).toFixed(2)}t</span>
        <span className="label">Carbon saved (CO₂)</span>
      </div>
      <div className="card stat-card">
        <div className="top">
          <IconBadge icon="zap" tone="orange" />
        </div>
        <span className="value num orange">{summary.energyUsageKwh.toLocaleString()}</span>
        <span className="label">Energy usage (kWh)</span>
      </div>
      <div className="card stat-card">
        <div className="top">
          <IconBadge icon="insights" tone="purple" />
        </div>
        <span className="value num" style={{ color: "var(--purple)" }}>{summary.sustainabilityScore}</span>
        <span className="label">Sustainability score</span>
      </div>
    </div>
  );
}