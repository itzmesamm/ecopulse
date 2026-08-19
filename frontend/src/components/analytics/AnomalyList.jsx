import { Icon } from "../ui/Icon";

export default function AnomalyList({ anomalies }) {
  return (
    <div className="card panel">
      <div className="panel-head">
        <h3>Detected anomalies</h3>
        <span className="see-all">
          View all <Icon name="chevronRight" />
        </span>
      </div>
      {anomalies.map((a) => (
        <div className="anomaly-item" key={a.id}>
          <div className="anomaly-score">{a.score.toFixed(2)}</div>
          <div>
            <div className="rid">{a.resourceId}</div>
            <div className="msg">{a.message}</div>
            <div className="ts">{a.detectedAt}</div>
          </div>
        </div>
      ))}
    </div>
  );
}