import { Icon } from "../ui/Icon";

export default function GrantAccess({ policy, checklist }) {
  return (
    <div className="grant-grid">
      <div className="card grant-box">
        <h4>1. Attach this read-only policy</h4>
        <div className="code-block">{policy}</div>
        <div className="callout">
          <Icon name="shield" style={{ display: "inline", width: 14, height: 14, marginRight: 6 }} />
          Read-only scope — Veya can never modify resources with this policy alone.
        </div>
      </div>

      <div className="card grant-box">
        <h4>2. Access checklist</h4>
        {checklist.map((c) => (
          <div className={`check-item ${c.status}`} key={c.id}>
            <div className="ic">
              <Icon name={c.status === "ok" ? "check" : "clock"} />
            </div>
            {c.label}
          </div>
        ))}
      </div>
    </div>
  );
}
