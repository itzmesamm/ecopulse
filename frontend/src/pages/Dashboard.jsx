import { useEffect, useState } from "react";
import AppShell from "../components/layout/AppShell";
import Topbar from "../components/layout/Topbar";
import StatCard from "../components/dashboard/StatCard";
import CostTrendChart from "../components/dashboard/CostTrendChart";
import AttentionPanel from "../components/dashboard/AttentionPanel";
import RemediationHistory from "../components/dashboard/RemediationHistory";
import InsightCard from "../components/dashboard/InsightCard";
import OptimizationProgress from "../components/dashboard/OptimizationProgress";
import WasteByCategory from "../components/dashboard/WasteByCategory";
import AssistantFab from "../components/dashboard/AssistantFab";
import AssistantPanel from "../components/dashboard/AssistantPanel";
import { Icon } from "../components/ui/Icon";
import { api } from "../services/api";
import { useUser } from "../context/UserContext";

const RANGES = ["7 days", "30 days", "90 days"];
const RANGE_DAYS = { "7 days": 7, "30 days": 30, "90 days": 90 };

export default function Dashboard() {
  const { account } = useUser();
  const [stats, setStats] = useState(null);
  const [trend, setTrend] = useState(null);
  const [attention, setAttention] = useState([]);
  const [history, setHistory] = useState([]);
  const [insight, setInsight] = useState(null);
  const [goals, setGoals] = useState([]);
  const [waste, setWaste] = useState([]);
  const [range, setRange] = useState("30 days");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [assistantOpen, setAssistantOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");

    Promise.all([
      api.getStatCards(),
      api.getCostTrend(RANGE_DAYS[range] || 30),
      api.getAttentionItems(),
      api.getRemediationHistory(),
      api.getAiInsight(),
      api.getOptimizationProgress(),
      api.getWasteByCategory(),
    ])
      .then(([s, t, a, h, i, g, w]) => {
        if (cancelled) return;
        setStats(s);
        setTrend(t);
        setAttention(a);
        setHistory(h);
        setInsight(i);
        setGoals(g);
        setWaste(w);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message || "Failed to load dashboard");
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [range]);

  return (
    <AppShell>
      <Topbar title="Overview" />

      {error && (
        <div style={{ color: "var(--red)", fontSize: 13, marginBottom: 12 }}>{error}</div>
      )}

      <div className="welcome-row">
        <div>
          <div style={{ color: "var(--text-2)", fontSize: 13.5 }}>
            Welcome back !! Here's how {account?.name || "your workspace"} is trending.
          </div>
        </div>
        <div className="selects">
          {RANGES.map((r) => (
            <button
              key={r}
              type="button"
              className="chip-select"
              onClick={() => setRange(r)}
              style={
                r === range
                  ? { background: "var(--text)", color: "var(--bg)", borderColor: "var(--text)" }
                  : undefined
              }
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      <div className="stat-row">
        {loading || !stats
          ? Array.from({ length: 4 }).map((_, i) => (
              <div className="card stat-card" key={i} aria-hidden="true">
                <div style={{ opacity: 0.4 }}>Loading…</div>
              </div>
            ))
          : stats.map((s) => (
              <StatCard
                key={s.id}
                label={s.label}
                value={s.value}
                icon={s.icon}
                tone={s.tone}
                pill={s.pill}
                valueTone={s.tone !== "blue" ? s.tone : undefined}
              />
            ))}
      </div>

      <div className="mid-row">
        <div className="card panel">
          <div className="panel-head">
            <h3>Cost trend &amp; forecast</h3>
            <span className="see-all">
              <Icon name="analytics" /> 90-day forecast
            </span>
          </div>
          <CostTrendChart data={trend} />
        </div>

        {attention.length > 0 && <AttentionPanel items={attention} />}
      </div>

      <div className="bottom-row" style={{ marginBottom: 16 }}>
        {history.length > 0 && <RemediationHistory items={history} />}
        {insight && <InsightCard insight={insight} />}
      </div>

      <div className="bottom-row">
        {goals.length > 0 && <OptimizationProgress goals={goals} />}
        {waste.length > 0 && <WasteByCategory categories={waste} />}
      </div>

      <AssistantFab onClick={() => setAssistantOpen(true)} />
      <AssistantPanel open={assistantOpen} onClose={() => setAssistantOpen(false)} />
    </AppShell>
  );
}
