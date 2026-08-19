import { useEffect, useMemo, useState } from "react";
import AppShell from "../components/layout/AppShell";
import Topbar from "../components/layout/Topbar";
import AlertItem from "../components/alerts/AlertItem";
import { api } from "../services/api";

const FILTERS = [
  { id: "all", label: "All" },
  { id: "anomaly", label: "Anomaly" },
  { id: "budget", label: "Budget" },
  { id: "policy", label: "Policy" },
];

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    api.getAlerts().then(setAlerts);
  }, []);

  const filtered = useMemo(
    () => (filter === "all" ? alerts : alerts.filter((a) => a.type === filter)),
    [alerts, filter]
  );

  return (
    <AppShell>
      <Topbar title="Alerts" />
      <div className="page-sub">Anomaly alerts, budget alerts, and policy violations across all connected accounts.</div>

      <div className="alert-filters">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            className="chip-select"
            onClick={() => setFilter(f.id)}
            style={
              f.id === filter
                ? { background: "var(--text)", color: "var(--bg)", borderColor: "var(--text)" }
                : undefined
            }
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="card panel">
        {filtered.length === 0 ? (
          <div style={{ color: "var(--text-2)", fontSize: 13.5, padding: "20px 0" }}>
            No alerts in this category.
          </div>
        ) : (
          filtered.map((a) => <AlertItem key={a.id} alert={a} />)
        )}
      </div>
    </AppShell>
  );
}