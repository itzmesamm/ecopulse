const TONE_VAR = {
  orange: "var(--orange)",
  blue: "var(--blue)",
  purple: "var(--purple)",
  teal: "var(--teal)",
  green: "var(--green)",
  red: "var(--red)",
};

export default function EsgBreakdown({ categories }) {
  return (
    <div className="card panel">
      <div className="panel-head">
        <h3>Carbon impact by category</h3>
      </div>
      <div className="bar-cluster">
        {categories.map((c) => (
          <div className="bar-col" key={c.id}>
            <span className="pct" style={{ color: TONE_VAR[c.tone] }}>
              {c.pct}%
            </span>
            <div
              className="bar-shape"
              style={{ height: `${c.pct * 1.3}px`, background: TONE_VAR[c.tone] }}
            />
            <span className="lbl">{c.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}