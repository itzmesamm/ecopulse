import { IconBadge, Pill } from "../ui/Pill";

const STATUS_TONE = { pending: "orange", executed: "green", rejected: "red" };
const STATUS_LABEL = { pending: "Pending", executed: "Executed", rejected: "Rejected" };

export default function RecommendationCard({ rec, onApprove, onReject }) {
  const confidencePct = Math.round(rec.confidence * 100);

  return (
    <div className="card reco-card">
      <div className="reco-top">
        <div className="l">
          <IconBadge icon={rec.icon} tone={rec.tone} />
          <div>
            <div className="rid">{rec.resourceId}</div>
            <div className="action">{rec.suggestedAction}</div>
          </div>
        </div>
        <Pill tone={STATUS_TONE[rec.status]}>{STATUS_LABEL[rec.status]}</Pill>
      </div>

      <p className="reco-cause">{rec.rootCause}</p>

      <div className="reco-meta">
        <div className="item">
          <span className="k">Savings</span>
          <span className="v orange">${rec.dollarSavings}/mo</span>
        </div>
        <div className="item">
          <span className="k">Carbon</span>
          <span className="v teal">{rec.carbonSavingsKg} kg CO₂</span>
        </div>
        <div className="item">
          <span className="k">Confidence</span>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div className="confidence-track">
              <div className="confidence-fill" style={{ width: `${confidencePct}%` }} />
            </div>
            <span className="v" style={{ fontSize: 12.5 }}>{confidencePct}%</span>
          </div>
        </div>
      </div>

      {rec.status === "pending" && (
        <div className="reco-actions">
          <button type="button" className="btn btn-primary" onClick={() => onApprove?.(rec.id)}>
            Approve action
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => onReject?.(rec.id)}>
            Dismiss
          </button>
        </div>
      )}
    </div>
  );
}