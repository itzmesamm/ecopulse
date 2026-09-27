import { Icon } from "../ui/Icon";
import { Pill } from "../ui/Pill";

export default function RemediationHistory({ items }) {
  return (
    <div className="card panel">
      <div className="panel-head">
        <h3>Remediation history</h3>
        <span className="see-all">
          View all <Icon name="chevronRight" />
        </span>
      </div>

      {items.map((item) => (
        <div className="table-row" key={item.id}>
          <div className="l">
            <div className="row-icon">
              <Icon name={item.icon} />
            </div>
            <div>
              <div className="rid">{item.title}</div>
              <div className="sub">{item.sub}</div>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <Pill tone={item.tone}>{item.status}</Pill>
            <div className="amt">{item.amount}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
