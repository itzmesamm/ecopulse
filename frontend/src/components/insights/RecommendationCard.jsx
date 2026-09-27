import { IconBadge, Pill } from "../ui/Pill";

const STATUS_TONE = { pending: "orange", executed: "green", rejected: "red" };
const STATUS_LABEL = { pending: "Pending", executed: "Executed", rejected: "Rejected" };

const PRIORITY_TONE = { high: "red", medium: "orange", low: "teal" };
const PRIORITY_LABEL = { high: "High priority", medium: "Medium priority", low: "Low priority" };

const RESOURCE_TYPE_LABEL = { gpu: "GPU", compute: "Compute", storage: "Storage", k8s: "Kubernetes" };

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

      <div className="reco-tags">
        <Pill tone={PRIORITY_TONE[rec.priority]}>{PRIORITY_LABEL[rec.priority]}</Pill>
        <span className="tag-mini">{RESOURCE_TYPE_LABEL[rec.resourceType] || rec.resourceType}</span>
        {rec.gpuModel && <span className="tag-mini">{rec.gpuModel}</span>}
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
          <div className="confidence-wrap">
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