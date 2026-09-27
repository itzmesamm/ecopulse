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
  const [assistantQuestion, setAssistantQuestion] = useState("");
  const [assistantAnswer, setAssistantAnswer] = useState("");
  const [assistantBusy, setAssistantBusy] = useState(false);

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

  async function askAssistant(event) {
    event.preventDefault();
    const question = assistantQuestion.trim();
    if (!question || assistantBusy) return;
    setAssistantBusy(true);
    setAssistantAnswer("");
    try {
      const response = await api.askAssistant(question);
      setAssistantAnswer(response.answer || response.message || JSON.stringify(response));
    } catch (err) {
      setAssistantAnswer(err.message || "Assistant unavailable");
    } finally {
      setAssistantBusy(false);
    }
  }

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

      {assistantOpen && (
        <div className="card panel" style={{ position: "fixed", right: 24, bottom: 96, width: 360, zIndex: 40 }}>
          <div className="panel-head">
            <h3>Ask Veya</h3>
            <button type="button" className="btn btn-ghost" onClick={() => setAssistantOpen(false)}>
              Close
            </button>
          </div>
          <form onSubmit={askAssistant}>
            <textarea
              value={assistantQuestion}
              onChange={(e) => setAssistantQuestion(e.target.value)}
              placeholder="Ask about waste, forecasts, GPU idle time…"
              rows={3}
              style={{ width: "100%", marginBottom: 8 }}
            />
            <button type="submit" className="btn btn-primary" disabled={assistantBusy}>
              {assistantBusy ? "Thinking…" : "Ask"}
            </button>
          </form>
          {assistantAnswer && (
            <p style={{ marginTop: 12, color: "var(--text-2)", whiteSpace: "pre-wrap", fontSize: 13.5 }}>
              {assistantAnswer}
            </p>
          )}
        </div>
      )}

      <AssistantFab onClick={() => setAssistantOpen((open) => !open)} />
    </AppShell>
  );
}
