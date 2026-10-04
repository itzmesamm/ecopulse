import { useEffect, useMemo, useState } from "react";
import AppShell from "../components/layout/AppShell";
import Topbar from "../components/layout/Topbar";
import InsightCard from "../components/dashboard/InsightCard";
import RecommendationCard from "../components/insights/RecommendationCard";
import SortControl from "../components/insights/SortControl";
import { api } from "../services/api";
import { useUser } from "../context/UserContext";
import { Icon } from "../components/ui/Icon";

const PRIORITY_RANK = { high: 3, medium: 2, low: 1 };
const SUGGESTED_QUESTIONS = [
  "Which idle GPUs could we stop to reduce monthly spend?",
  "How can we right-size compute without affecting production?",
  "Which storage resources look safe to clean up?",
  "How can we improve Kubernetes utilization in staging?",
  "Recommend a utilization technique and integrate it in this prototype.",
];

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
  const { user } = useUser();
  const [insight, setInsight] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [filters, setFilters] = useState({ priority: "all", resourceType: "all", savingsOrder: "highest" });
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [batchSize, setBatchSize] = useState(1);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [automationPlans, setAutomationPlans] = useState(() => new Map());
  const [prompt, setPrompt] = useState("");
  const [assistantReply, setAssistantReply] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.getAiInsight(), api.getRecommendations(), api.getAutomationPlans()])
      .then(([nextInsight, nextRecommendations, storedPlans]) => {
        if (cancelled) return;
        setInsight(nextInsight);
        setRecommendations(nextRecommendations);
        setAutomationPlans(new Map(storedPlans.map((item) => [item.recommendation_id, item.plan])));
      })
      .catch((requestError) => {
        if (!cancelled) setError(requestError.message || "Could not load recommendations.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const filtered = recommendations.filter((item) =>
    (filters.priority === "all" || item.priority === filters.priority)
    && (filters.resourceType === "all" || item.resourceType === filters.resourceType)
  );
  const sorted = useMemo(() => sortRecommendations(filtered, filters.savingsOrder), [
    recommendations,
    filters.priority,
    filters.resourceType,
    filters.savingsOrder,
  ]);

  const resourceTypes = [...new Set(recommendations.map((item) => item.resourceType).filter(Boolean))].sort();
  const canApprove = ["admin", "approver"].includes(String(user?.role || "").toLowerCase());

  async function handleGenerate() {
    setGenerating(true);
    setError("");
    setNotice("");
    try {
      const generated = await api.generateRecommendations(batchSize);
      setRecommendations((current) => {
        const generatedIds = new Set(generated.map((item) => item.id));
        return [...generated, ...current.filter((item) => !generatedIds.has(item.id))];
      });
      setNotice(`${generated.length} recommendation${generated.length === 1 ? "" : "s"} generated.`);
    } catch (requestError) {
      setError(requestError.message || "Recommendation generation failed.");
    } finally {
      setGenerating(false);
    }
  }

  async function handleRecommendationPrompt(question) {
    const asked = question.trim();
    if (!asked || generating) return;

    setGenerating(true);
    setError("");
    setNotice("");
    setAssistantReply("");
    setPrompt("");

    const [assistantResult, recommendationResult] = await Promise.allSettled([
      api.askAssistant(asked),
      api.generateRecommendations(batchSize, asked),
    ]);

    if (assistantResult.status === "fulfilled") {
      setAssistantReply(assistantResult.value.answer || "Veya did not return a response.");
    } else {
      setError(assistantResult.reason.message || "Veya could not answer this question.");
    }

    if (recommendationResult.status === "fulfilled") {
      const generated = recommendationResult.value;
      setRecommendations((current) => {
        const generatedIds = new Set(generated.map((item) => item.id));
        return [...generated, ...current.filter((item) => !generatedIds.has(item.id))];
      });
      setNotice(`${generated.length} recommendation${generated.length === 1 ? "" : "s"} generated from your workspace findings.`);
    } else {
      setError((current) => [current, recommendationResult.reason.message || "Could not generate recommendations."].filter(Boolean).join(" "));
    }

    setGenerating(false);
  }

  async function handleBuildAutomationPlan(id) {
    setBusyId(id);
    setError("");
    setNotice("");
    try {
      const response = await api.prepareAutomationPlan([id], user?.role);
      const outcome = response.outcomes?.find((item) => item.recommendation_id === id);
      if (!outcome?.plan) throw new Error(outcome?.error || "The backend did not return an automation plan.");
      setAutomationPlans((current) => new Map(current).set(id, outcome.plan));
      setNotice("Automation plan stored. The plan is dry-run only and made no cloud changes.");
    } catch (requestError) {
      setError(requestError.message || "Could not create the automation plan.");
    } finally {
      setBusyId(null);
    }
  }

  function updateStatus(id, status) {
    setRecommendations((list) => list.map((item) => item.id === id ? { ...item, status } : item));
  }

  async function handleSimulate(id) {
    setBusyId(id);
    setError("");
    setNotice("");
    try {
      const result = await api.processRemediation([id], user?.role);
      const outcome = result.outcomes?.find((item) => item.recommendation_id === id);
      if (!outcome) throw new Error("The backend did not return an outcome for this recommendation.");
      updateStatus(id, outcome.new_status);
      if (outcome.automation_plan) setAutomationPlans((current) => new Map(current).set(id, outcome.automation_plan));
      setNotice(outcome.result);
    } catch (requestError) {
      setError(requestError.message || "Could not simulate this action.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleApprove(id) {
    setBusyId(id);
    setError("");
    setNotice("");
    try {
      const result = await api.approveRemediation([id], user?.role);
      const outcome = result.outcomes?.find((item) => item.recommendation_id === id);
      if (!outcome) throw new Error("The backend did not return an outcome for this recommendation.");
      updateStatus(id, outcome.new_status);
      if (outcome.automation_plan) setAutomationPlans((current) => new Map(current).set(id, outcome.automation_plan));
      setNotice(outcome.result);
    } catch (requestError) {
      setError(requestError.message || "Could not approve this action.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleExecuteLive(id) {
    setBusyId(id);
    setError("");
    setNotice("");
    try {
      const rec = recommendations.find((item) => item.id === id);
      if (!rec) throw new Error("Recommendation not found on this page.");
      const result = await api.approveRemediation([id], user?.role, false, { [id]: `STOP ${rec.resourceId}` });
      const outcome = result.outcomes?.find((item) => item.recommendation_id === id);
      if (!outcome) throw new Error("The backend did not return an execution outcome.");
      updateStatus(id, outcome.new_status);
      setNotice(outcome.result);
    } catch (requestError) {
      setError(requestError.message || "Could not execute the approved action.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleDismiss(id) {
    setBusyId(id);
    setError("");
    setNotice("");
    try {
      await api.dismissRecommendation(id);
      updateStatus(id, "rejected");
      setNotice("Recommendation dismissed.");
    } catch (requestError) {
      setError(requestError.message || "Could not dismiss this recommendation.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <AppShell>
      <Topbar title="AI Insights" />
      <div className="page-sub">
        Recommendations grounded in your workspace findings, with reviewable dry-run remediation.
      </div>

      <div className="insights-actions">
        <span className="dry-run-note">Remediation stays in dry-run mode; no cloud resources are changed.</span>
        <div className="generate-controls">
          <label className="generate-count" htmlFor="recommendation-batch-size">
            <span>Per run</span>
            <select
              id="recommendation-batch-size"
              className="sort-select"
              value={batchSize}
              onChange={(event) => setBatchSize(Number(event.target.value))}
              disabled={generating}
            >
              <option value={1}>1</option>
              <option value={3}>3</option>
              <option value={5}>5</option>
            </select>
          </label>
          <button type="button" className="btn btn-primary" onClick={handleGenerate} disabled={generating}>
            <Icon name="insights" />
            {generating ? "Generating…" : "Generate recommendations"}
          </button>
        </div>
      </div>

      <section className="recommendation-assistant card" aria-labelledby="recommendation-assistant-title">
        <div className="recommendation-assistant-heading">
          <div>
            <h2 id="recommendation-assistant-title">Ask Veya for a recommendation</h2>
            <p>Choose a question to get a workspace-grounded answer and generate recommendations.</p>
          </div>
          <span className="prototype-label">Dry-run workflow</span>
        </div>
        <div className="recommendation-prompts">
          {SUGGESTED_QUESTIONS.map((question) => (
            <button
              key={question}
              type="button"
              className="recommendation-prompt"
              disabled={generating}
              onClick={() => handleRecommendationPrompt(question)}
            >
              {question}
            </button>
          ))}
        </div>
        <form
          className="recommendation-prompt-form"
          onSubmit={(event) => {
            event.preventDefault();
            handleRecommendationPrompt(prompt);
          }}
        >
          <label className="sr-only" htmlFor="insights-question">Ask Veya for a recommendation</label>
          <input
            id="insights-question"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Ask about a utilization technique..."
            disabled={generating}
          />
          <button type="submit" className="btn btn-primary" disabled={generating || !prompt.trim()}>
            <Icon name={generating ? "loading" : "send"} />
            {generating ? "Working…" : "Ask & recommend"}
          </button>
        </form>
        {assistantReply && (
          <div className="recommendation-answer" role="status">
            <strong>Veya</strong>
            <p>{assistantReply}</p>
          </div>
        )}
      </section>

      {error && <div className="workflow-message error" role="alert">{error}</div>}
      {notice && <div className="workflow-message" role="status">{notice}</div>}

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

      {loading && <p className="workflow-empty">Loading recommendations…</p>}
      {!loading && !sorted.length && (
        <p className="workflow-empty">No generated recommendations yet. Run waste analysis first, then generate recommendations.</p>
      )}
      {sorted.map((rec) => (
        <RecommendationCard
          key={rec.id}
          rec={rec}
          busy={busyId === rec.id}
          canApprove={canApprove}
          canExecuteLive={String(user?.role || "").toLowerCase() === "admin"}
          automationPlan={automationPlans.get(rec.id)}
          onSimulate={handleSimulate}
          onApprove={handleApprove}
          onExecuteLive={handleExecuteLive}
          onDismiss={handleDismiss}
          onBuildAutomationPlan={handleBuildAutomationPlan}
        />
      ))}
    </AppShell>
  );
}