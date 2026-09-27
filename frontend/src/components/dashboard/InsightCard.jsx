import { Icon } from "../ui/Icon";

export default function InsightCard({ insight }) {
  return (
    <div className="insight-card">
      <div className="badge">
        <Icon name="insights" color="#fff" />
      </div>
      <h3>{insight.title}</h3>
      <p>{insight.body}</p>
      <div className="link">
        {insight.cta} <Icon name="chevronRight" />
      </div>
    </div>
  );
}
