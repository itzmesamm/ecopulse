import { Icon } from "./Icon";

export function Pill({ tone = "blue", direction, children }) {
  return (
    <span className={`pill ${tone}`}>
      {direction === "up" && <Icon name="up" />}
      {direction === "down" && <Icon name="down" />}
      {children}
    </span>
  );
}

export function IconBadge({ icon, tone = "blue", size }) {
  return (
    <div className={`icon-badge ${tone}`} style={size ? { width: size, height: size } : undefined}>
      <Icon name={icon} />
    </div>
  );
}
