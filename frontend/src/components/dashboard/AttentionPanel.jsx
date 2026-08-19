import { IconBadge } from "../ui/Pill";
import { Icon } from "../ui/Icon";

export default function AttentionPanel({ items }) {
  return (
    <div className="card panel">
      <div className="panel-head">
        <h3>Needs your attention</h3>
        <span className="see-all">
          View all <Icon name="chevronRight" />
        </span>
      </div>

      {items.map((item) => (
        <div className="rec-item" key={item.id}>
          <div className="l">
            <IconBadge icon={item.icon} tone={item.tone} />
            <div>
              <div className="title">{item.title}</div>
              <div className="desc">{item.desc}</div>
            </div>
          </div>
          <div className="cost">{item.cost}</div>
        </div>
      ))}
    </div>
  );
}
