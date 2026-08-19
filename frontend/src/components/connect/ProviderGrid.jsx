import { Icon } from "../ui/Icon";

export default function ProviderGrid({ providers, selected, onSelect }) {
  return (
    <div className="provider-grid">
      {providers.map((p) => (
        <div
          key={p.id}
          className={`card provider-card ${selected === p.id ? "sel" : ""}`}
          onClick={() => onSelect(p.id)}
          role="button"
          tabIndex={0}
        >
          {p.recommended && <span className="badge">Recommended</span>}
          <div className="icon-badge blue icon" style={{ width: 40, height: 40 }}>
            <Icon name="cloud" />
          </div>
          <div className="pname">{p.name}</div>
          <p>{p.desc}</p>
        </div>
      ))}
    </div>
  );
}
