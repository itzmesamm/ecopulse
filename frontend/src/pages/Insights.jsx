import { useEffect, useState } from "react";
import AppShell from "../components/layout/AppShell";
import Topbar from "../components/layout/Topbar";
import InsightCard from "../components/dashboard/InsightCard";
import RecommendationCard from "../components/insights/RecommendationCard";
import { api } from "../services/api";

export default function Insights() {
  const [insight, setInsight] = useState(null);
  const [recommendations, setRecommendations] = useState([]);

  useEffect(() => {
    api.getAiInsight().then(setInsight);
    api.getRecommendations().then(setRecommendations);
  }, []);

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

      {recommendations.map((rec) => (
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