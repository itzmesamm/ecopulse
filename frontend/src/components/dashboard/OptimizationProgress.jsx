function formatValue(v, unit) {
  const n = Number(v) || 0;
  if (unit) {
    const suffix = unit.includes("CO") ? "t" : unit;
    return `${n}${suffix}`;
  }
  return `$${n.toLocaleString()}`;
}

export default function OptimizationProgress({ goals }) {
  return (
    <div className="card panel">
      <div className="panel-head">
        <h3>Optimization goals</h3>
      </div>

      {goals.map((goal) => {
        const pct = Math.min(100, Math.round((goal.current / goal.target) * 100));
        return (
          <div className="progress-block" key={goal.id}>
            <div className="ptop">
              <span>{goal.label}</span>
              <b>
                {formatValue(goal.current, goal.unit)} / {formatValue(goal.target, goal.unit)}
              </b>
            </div>
            <div className="progress-track">
              <div
                className={`progress-fill ${goal.tone}`}
                style={{ width: `${pct}%` }}
              >
                <span className="pct">{pct}%</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
