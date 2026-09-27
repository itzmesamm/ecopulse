const TONE_VAR = {
  orange: "var(--orange)",
  blue: "var(--blue)",
  purple: "var(--purple)",
  teal: "var(--teal)",
  green: "var(--green)",
  red: "var(--red)",
};

export default function ServiceBreakdownChart({ services }) {
  const max = Math.max(...services.map((s) => s.cost));

  return (
    <div className="card panel">
      <div className="panel-head">
        <h3>Cost by service</h3>
      </div>
      {services.map((s) => (
        <div className="svc-row" key={s.id}>
          <span className="dot" style={{ background: TONE_VAR[s.tone] }} />
          <span className="name">{s.label}</span>
          <div className="track">
            <div
              className="fill"
              style={{ width: `${(s.cost / max) * 100}%`, background: TONE_VAR[s.tone] }}
            />
          </div>
          <span className="amt">${s.cost.toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}