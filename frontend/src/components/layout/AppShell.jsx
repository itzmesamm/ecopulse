import { useState } from "react";
import Sidebar from "./Sidebar";

export default function AppShell({ children }) {
  const [expanded, setExpanded] = useState(() => localStorage.getItem("sidebar_expanded") === "true");

  function toggleSidebar() {
    setExpanded((current) => {
      const next = !current;
      localStorage.setItem("sidebar_expanded", String(next));
      return next;
    });
  }

  return (
    <div className={`app-shell ${expanded ? "sidebar-expanded" : "sidebar-collapsed"}`}>
      <Sidebar expanded={expanded} onToggle={toggleSidebar} />
      <main className="main">{children}</main>
    </div>
  );
}
