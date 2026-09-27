import { useEffect, useMemo, useState } from "react";
import AppShell from "../components/layout/AppShell";
import Topbar from "../components/layout/Topbar";
import InsightCard from "../components/dashboard/InsightCard";
import RecommendationCard from "../components/insights/RecommendationCard";
import SortControl from "../components/insights/SortControl";
import { api } from "../services/api";

const PRIORITY_RANK = { high: 3, medium: 2, low: 1 };

function sortRecommendations(list, savingsOrder) {
  const copy = [...list];
  return copy.sort(
    (a, b) =>
      (savingsOrder === "lowest" ? 1 : -1) * (a.dollarSavings - b.dollarSavings) ||
      (PRIORITY_RANK[b.priority] || 0) - (PRIORITY_RANK[a.priority] || 0) ||
      String(a.id).localeCompare(String(b.id))
  );
}

export default function Insights() {
  const [insight, setInsight] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [filters, setFilters] = useState({ priority: "all", resourceType: "all", savingsOrder: "highest" });

  useEffect(() => {
    api.getAiInsight().then(setInsight);
    api.getRecommendations(filters).then(setRecommendations);
  }, [filters]);

  const sorted = useMemo(
    () => sortRecommendations(recommendations, filters.savingsOrder),
    [recommendations, filters.savingsOrder]
  );

  const resourceTypes = [...new Set(recommendations.map((item) => item.resourceType).filter(Boolean))].sort();

  function handleApprove(id) {
    setRecommendations((list) =>
      list.map((r) => (r.id === id ? { ...r, status: "executed" } : r))
    );
    api.updateRecommendationStatus(id, "executed");
  }

  function handleReject(id) {
    setRecommendations((list) =>
      list.map((r) => (r.id === id ? { ...r, status: "rejected" } : r))
    );
    api.updateRecommendationStatus(id, "rejected");
  }

  return (
    <AppShell>
      <Topbar title="AI Insights" />
      <div className="page-sub">
        Grounded, RAG-backed explanations of root cause, cost &amp; carbon impact, and the fix to apply.
      </div>

      {insight && (
        <div style={{ marginBottom: 20, maxWidth: 640 }}>
          <InsightCard insight={insight} />
        </div>
      )}

      <SortControl
        priority={filters.priority}
        resourceType={filters.resourceType}
        savingsOrder={filters.savingsOrder}
        resourceTypes={resourceTypes}
        onChange={(change) => setFilters((current) => ({ ...current, ...change }))}
      />

      {sorted.map((rec) => (
        <RecommendationCard
          key={rec.id}
          rec={rec}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      ))}
    </AppShell>
  );
}