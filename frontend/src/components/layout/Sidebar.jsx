import { useNavigate, useLocation } from "react-router-dom";
import { Icon } from "../ui/Icon";
import { useUser } from "../../context/UserContext";

const NAV_ITEMS = [
  { id: "dashboard", icon: "dashboard", label: "Dashboard", path: "/dashboard" },
  { id: "analytics", icon: "analytics", label: "Analytics", path: "/analytics" },
  { id: "insights", icon: "insights", label: "AI Insights", path: "/insights" },
  { id: "alerts", icon: "alerts", label: "Alerts", path: "/alerts", badge: true },
  { id: "greenops", icon: "greenops", label: "GreenOps", path: "/greenops" },
];

export default function Sidebar({ expanded, onToggle }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useUser();

  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <div className="mark" aria-hidden="true">
        <img src="/logo.png" alt="" />
      </div>

      <button type="button" className="sidebar-toggle" onClick={onToggle} aria-label={expanded ? "Collapse sidebar" : "Expand sidebar"} title={expanded ? "Collapse sidebar" : "Expand sidebar"}>
        <Icon name="chevronRight" />
      </button>

      {NAV_ITEMS.map((item) => (
        <button
          key={item.id}
          type="button"
          className={`snav ${location.pathname === item.path ? "active" : ""}`}
          onClick={() => navigate(item.path)}
          title={item.label}
          aria-label={item.label}
        >
          <Icon name={item.icon} />
          <span className="snav-label">{item.label}</span>
          {item.badge && <span className="dot-badge" />}
        </button>
      ))}

      <div className="spacer" />

      <button
        type="button"
        className={`snav ${location.pathname === "/settings" ? "active" : ""}`}
        onClick={() => navigate("/settings")}
        title="Settings"
        aria-label="Settings"
      >
        <Icon name="settings" />
        <span className="snav-label">Settings</span>
      </button>
      <button type="button" className={`avatar ${location.pathname === "/profile" ? "active" : ""}`} title={user.name} aria-label={`Open profile for ${user.name}`} onClick={() => navigate("/profile")}>
        <span className="avatar-initials">{user.initials}</span>
        <span className="avatar-label">{user.name}</span>
      </button>
    </aside>
  );
}
