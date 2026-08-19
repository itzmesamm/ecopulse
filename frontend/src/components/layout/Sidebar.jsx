import { useNavigate, useLocation } from "react-router-dom";
import { Icon } from "../ui/Icon";
import { currentUser } from "../../data/mockData";

const NAV_ITEMS = [
  { id: "dashboard", icon: "dashboard", label: "Dashboard", path: "/dashboard" },
  { id: "analytics", icon: "analytics", label: "Analytics", path: "/analytics" },
  { id: "insights", icon: "insights", label: "AI Insights", path: "/insights" },
  { id: "alerts", icon: "alerts", label: "Alerts", path: "/alerts", badge: true },
  { id: "greenops", icon: "greenops", label: "GreenOps", path: "/greenops" },
];

export default function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <aside className="sidebar">
      <div className="mark" aria-hidden="true">
        <span />
      </div>

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
      </button>
      <button type="button" className="avatar" title={currentUser.name} aria-label={currentUser.name}>
        {currentUser.initials}
      </button>
    </aside>
  );
}