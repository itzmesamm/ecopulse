import { useState } from "react";
import { IconBadge, Pill } from "../ui/Pill";

const STATUS_TONE = {
  pending: "orange",
  pending_approval: "orange",
  simulated: "teal",
  executed: "green",
  rejected: "red",
  denied: "red",
};
const STATUS_LABEL = {
  pending: "Pending review",
  pending_approval: "Approval required",
  simulated: "Dry run complete",
  executed: "Executed",
  rejected: "Dismissed",
  denied: "Approval denied",
};

const PRIORITY_TONE = { high: "red", medium: "orange", low: "teal" };
const PRIORITY_LABEL = { high: "High priority", medium: "Medium priority", low: "Low priority" };

const RESOURCE_TYPE_LABEL = { gpu: "GPU", compute: "Compute", storage: "Storage", k8s: "Kubernetes" };
const EC2_STOP_ACTION_LABEL = "stop idle ec2 instance";

export default function RecommendationCard({ rec, busy, canApprove, canExecuteLive, automationPlan, onSimulate, onApprove, onExecuteLive, onDismiss, onBuildAutomationPlan }) {
  const [confirmLive, setConfirmLive] = useState(false);
  const [executionPhrase, setExecutionPhrase] = useState("");
  const confidencePct = Math.max(0, Math.min(100, Math.round(rec.confidence * 100)));
  const requiredPhrase = `STOP ${rec.resourceId}`;
  const supportsLiveStop = canExecuteLive
    && String(rec.resourceType).toLowerCase() === "ec2"
    && /^i-[0-9a-f]{8,17}$/i.test(String(rec.resourceId))
    && String(rec.suggestedAction).trim().toLowerCase() === EC2_STOP_ACTION_LABEL;

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
        <Pill tone={automationPlan ? "teal" : STATUS_TONE[rec.status]}>
          {automationPlan ? "Plan ready · dry-run only" : STATUS_LABEL[rec.status]}
        </Pill>
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
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => onSimulate?.(rec.id)}>
            {busy ? "Simulating…" : "Simulate remediation"}
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={busy}
            onClick={() => onBuildAutomationPlan?.(rec.id)}
          >
            {busy ? "Preparing plan…" : automationPlan ? "Refresh automation plan" : "Build automation plan"}
          </button>
          <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => onDismiss?.(rec.id)}>
            Dismiss
          </button>
        </div>
      )}
      {rec.status === "pending_approval" && (
        <div className="reco-actions">
          {canApprove ? (
            <button type="button" className="btn btn-primary" disabled={busy} onClick={() => onApprove?.(rec.id)}>
              {busy ? "Approving…" : "Approve & simulate"}
            </button>
          ) : (
            <span className="approval-hint">An admin or approver must review this production action.</span>
          )}
          {supportsLiveStop && (
            <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => setConfirmLive((current) => !current)}>
              {confirmLive ? "Cancel live stop" : "Review live stop"}
            </button>
          )}
          <button
            type="button"
            className="btn btn-ghost"
            disabled={busy}
            onClick={() => onBuildAutomationPlan?.(rec.id)}
          >
            {busy ? "Preparing plan…" : automationPlan ? "Refresh automation plan" : "Build automation plan"}
          </button>
          <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => onDismiss?.(rec.id)}>
            Dismiss
          </button>
        </div>
      )}
      {(rec.status === "pending" || rec.status === "pending_approval") && confirmLive && supportsLiveStop && (
        <form
          className="live-execution-confirm"
          onSubmit={(event) => {
            event.preventDefault();
            onExecuteLive?.(rec.id);
            setConfirmLive(false);
            setExecutionPhrase("");
          }}
        >
          <strong>Stop {rec.resourceId} in AWS?</strong>
          <p>This is a live infrastructure change. The instance must be tagged EcoPulseAutomation=enabled. Type <code>{requiredPhrase}</code> to confirm.</p>
          <div className="live-execution-controls">
            <input
              aria-label={`Type ${requiredPhrase} to confirm`}
              value={executionPhrase}
              onChange={(event) => setExecutionPhrase(event.target.value)}
              autoComplete="off"
              disabled={busy}
            />
            <button type="submit" className="btn btn-primary" disabled={busy || executionPhrase !== requiredPhrase}>
              {busy ? "Executing…" : "Stop instance"}
            </button>
          </div>
        </form>
      )}
      {automationPlan && (
        <section className="automation-preview" aria-label={`Automation preview for ${rec.resourceId}`}>
          <div className="automation-preview-heading">
            <IconBadge icon="zap" tone="teal" />
            <div>
              <strong>{automationPlan.strategy}</strong>
              <span>{automationPlan.service || rec.resourceType} · {automationPlan.environment} · dry-run only</span>
            </div>
          </div>
          <ol className="automation-steps">
            {automationPlan.steps.map((step, index) => (
              <li key={`${rec.id}-step-${index}`}>
                <span className="automation-step-number">{String(index + 1).padStart(2, "0")}</span>
                <div>
                  <strong>{index === 0 ? "Validate" : index === automationPlan.steps.length - 1 ? "Stage safely" : "Prepare change"}</strong>
                  <p>{step}</p>
                </div>
              </li>
            ))}
          </ol>
          <div className="automation-safeguards">
            <strong>Safety checks</strong>
            <ul>{automationPlan.safety_checks.map((check) => <li key={check}>{check}</li>)}</ul>
          </div>
          <p className="automation-rollback"><strong>Rollback:</strong> {automationPlan.rollback}</p>
          <div className="automation-impact">
            <span>Projected monthly savings <strong>${Number(automationPlan.estimated_monthly_savings_usd || 0).toFixed(2)}</strong></span>
            <span>Projected carbon reduction <strong>{rec.carbonSavingsKg} kg CO₂</strong></span>
          </div>
          <p className="automation-disabled-note">This plan is not executable. A separate, admin-approved EC2 stop is available only for the exact supported action and eligible tagged instances.</p>
        </section>
      )}
    </div>
  );
}