import { Icon } from "../ui/Icon";

const SEV_ICON = { critical: "alerts", warning: "hourglass", info: "check" };
const CHAN_ICON = { slack: "assistant", email: "mail" };

export default function AlertItem({ alert }) {
  return (
    <div className="alert-item">
      <div className={`alert-sev ${alert.severity}`}>
        <Icon name={SEV_ICON[alert.severity] || "alerts"} />
      </div>
      <div className="alert-body">
        <div className="alert-msg">{alert.message}</div>
        <div className="alert-meta">
          <span className="chan">
            <Icon name={CHAN_ICON[alert.channel] || "mail"} /> {alert.channel}
          </span>
          <span>·</span>
          <span>{alert.sentAt}</span>
        </div>
      </div>
    </div>
  );
}