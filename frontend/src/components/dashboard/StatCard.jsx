import { IconBadge, Pill } from "../ui/Pill";

export default function StatCard({ label, value, icon, tone, pill, valueTone }) {
  return (
    <div className="card stat-card">
      <div className="top">
        <IconBadge icon={icon} tone={tone} />
        {pill && (
          <Pill tone={pill.tone} direction={pill.direction}>
            {pill.text}
          </Pill>
        )}
      </div>
      <span className={`value num ${valueTone || ""}`}>{value}</span>
      <span className="label">{label}</span>
    </div>
  );
}
