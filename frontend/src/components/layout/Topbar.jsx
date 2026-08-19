import { Icon } from "../ui/Icon";
import ThemeToggle from "../ui/ThemeToggle";
import { currentUser } from "../../data/mockData";

export default function Topbar({ title }) {
  return (
    <div className="topbar">
      <h1>{title}</h1>

      <div className="search-box">
        <Icon name="search" />
        <input type="text" placeholder="Search resources, findings..." aria-label="Search" />
      </div>

      <div className="topbar-right">
        <ThemeToggle />

        <button type="button" className="topbar-icon" aria-label="Notifications">
          <Icon name="alerts" />
          <span className="dot-badge" />
        </button>

        <div className="profile-chip">
          <div className="av">{currentUser.initials}</div>
          <div>
            <div className="name">{currentUser.name}</div>
            <div className="role">{currentUser.role}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
