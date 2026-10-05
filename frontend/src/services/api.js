// Service layer for EcoPulse's frontend.
// Connects to FastAPI backend and transforms responses to match UI component contracts.

 import {
   statCards,
   costTrend,
   attentionItems,
   remediationHistory,
   aiInsight,
   optimizationProgress,
   wasteByCategory,
   currentUser,
   currentAccount,
   cloudProviders,
   iamPolicyJson,
   accessChecklist,
   serviceBreakdown,
   anomalies,
   forecastAccuracy,
   alerts,
   greenOpsSummary,
   esgBreakdown,
   connectedAccounts,
   notificationSettings,
   notificationChannels,
 } from "../data/mockData";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const MOCK_LATENCY_MS = 260;
const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA === "true";

function mockResolve(payload) {
  return new Promise((resolve) => setTimeout(() => resolve(payload), MOCK_LATENCY_MS));
}

function getAuthToken() {
  return localStorage.getItem("auth_token");
}

function getOrgId() {
  return localStorage.getItem("org_id");
}

function requireOrgId() {
  const orgId = getOrgId();
  if (!orgId) throw new Error("Not authenticated");
  return orgId;
}

function getHeaders() {
  const token = getAuthToken();
  return {
    "Content-Type": "application/json",
    ...(token && { Authorization: `Bearer ${token}` }),
  };
}

async function fetchAPI(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: { ...getHeaders(), ...options.headers },
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail = data.detail || response.statusText;
    const message = typeof detail === "string" ? detail : JSON.stringify(detail);
    throw new Error(message);
  }

  return data;
}

async function withFallback(fetcher, fallback) {
  if (USE_MOCK_DATA) return mockResolve(fallback);
  return fetcher();
}

function formatUsd(amount) {
  if (amount >= 1000) return `$${(amount / 1000).toFixed(1)}k`;
  return `$${Math.round(amount).toLocaleString()}`;
}

function wasteIcon(service = "") {
  const s = service.toLowerCase();
  if (s.includes("gpu")) return "server";
  if (s.includes("k8s") || s.includes("kubernetes") || s.includes("pod")) return "boxes";
  if (s.includes("s3") || s.includes("storage") || s.includes("volume")) return "database";
  return "monitor";
}

function wasteTone(service = "") {
  const s = service.toLowerCase();
  if (s.includes("gpu")) return "orange";
  if (s.includes("k8s") || s.includes("pod")) return "teal";
  if (s.includes("s3") || s.includes("storage")) return "purple";
  return "blue";
}

function transformStatCards(stats) {
  const cost = stats.total_monthly_cost || 0;
  const savings = stats.potential_monthly_savings || 0;
  const items = stats.total_waste_items || 0;
  const critical = stats.critical_items || 0;

  return [
    {
      id: "monthly-cost",
      label: "Monthly cloud cost",
      value: formatUsd(cost),
      icon: "creditCard",
      tone: "blue",
      pill: items > 0 ? { tone: "red", direction: "down", text: `${items} waste items` } : undefined,
    },
    {
      id: "savings-identified",
      label: "Savings identified",
      value: formatUsd(savings),
      icon: "zap",
      tone: "orange",
      pill: items > 0 ? { tone: "orange", direction: "up", text: `${items} findings` } : undefined,
    },
    {
      id: "carbon-saved",
      label: "Carbon saved",
      value: `${(savings * 0.00005).toFixed(1)}t`,
      icon: "leaf",
      tone: "teal",
      pill: { tone: "teal", text: "CO\u2082 estimate" },
    },
    {
      id: "needs-approval",
      label: "Needs approval",
      value: String(critical),
      icon: "hourglass",
      tone: "red",
      pill: critical > 0 ? { tone: "red", text: "Critical items" } : undefined,
    },
  ];
}

function transformCostTrend(trends) {
  if (!Array.isArray(trends) || trends.length === 0) {
    return { currentLabel: "$0", actual: [], forecast: [], labels: [] };
  }

  const costs = trends.map((t) => Number(t.cost) || 0);
  const labels = trends.map((t, i) => {
    const d = new Date(t.date);
    if (Number.isNaN(d.getTime())) return `D${i + 1}`;
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  });
  const split = Math.max(1, Math.floor(costs.length * 0.7));
  const actual = costs.slice(0, split);
  const lastActual = actual[actual.length - 1] || 0;
  const forecast = costs.slice(split);
  if (forecast.length === 0) {
    forecast.push(
      Math.round(lastActual * 0.92),
      Math.round(lastActual * 0.88),
      Math.round(lastActual * 0.84)
    );
  }

  return {
    currentLabel: formatUsd(lastActual),
    actual,
    forecast,
    labels,
  };
}

function transformAttentionItems(items) {
  return (Array.isArray(items) ? items : []).map((item) => ({
    id: item.id,
    title: item.resource_id || item.title,
    desc: `${item.waste_type?.replace(/_/g, " ") || "Waste"} · ${item.service || "unknown"}`,
    cost: `$${Math.round(item.estimated_monthly_waste_usd || 0)}/mo`,
    icon: wasteIcon(item.service),
    tone: wasteTone(item.service),
  }));
}

function transformRemediationHistory(actions) {
  const statusMap = {
    completed: { status: "Executed", tone: "green" },
    in_progress: { status: "In progress", tone: "orange" },
    pending: { status: "Pending", tone: "orange" },
    failed: { status: "Rejected", tone: "red" },
  };

  return (Array.isArray(actions) ? actions : []).map((action) => {
    const mapped = statusMap[action.status] || statusMap.pending;
    return {
      id: action.id,
      title: action.action_type?.replace(/_/g, " ") || "Remediation",
      sub: action.description || action.status,
      amount: `$${(action.estimated_savings_usd || 0).toFixed(2)}`,
      status: mapped.status,
      tone: mapped.tone,
      icon: "server",
      createdAt: action.created_at ? new Date(action.created_at).getTime() : 0,
    };
  }).sort((a, b) => b.createdAt - a.createdAt || String(b.id).localeCompare(String(a.id)));
}

function transformWasteByCategory(insights) {
  const entries = Array.isArray(insights)
    ? insights
    : Object.entries(insights || {}).map(([service, data]) => ({
        category: service,
        value: data.total_estimated_monthly_waste_usd,
        itemCount: data.waste_item_count,
      }));

  const total = entries.reduce((sum, e) => sum + (e.value || 0), 0) || 1;

  return entries.map((entry, i) => ({
    id: entry.category || `cat-${i}`,
    label: entry.category || "Unknown",
    pct: Math.round(((entry.value || 0) / total) * 100),
    tone: wasteTone(entry.category),
  }));
}

function transformCloudProviders(providers) {
  const descMap = {
    aws: "Cost Explorer + CloudWatch",
    gcp: "Billing export + Monitoring",
    azure: "Cost Management + Monitor",
  };

  return (Array.isArray(providers) ? providers : []).map((p) => ({
    id: p.id,
    name: p.name?.replace("Amazon Web Services", "AWS") || p.id.toUpperCase(),
    desc: p.desc || p.description || descMap[p.id] || "",
    recommended: p.id === "aws",
  }));
}

function transformAccessChecklist(items) {
  return (Array.isArray(items) ? items : []).map((item, i) => ({
    id: item.id || `check-${i}`,
    label: item.label || item.item,
    status: item.status === "verified" ? "ok" : item.status === "pending" ? "pending" : "ok",
  }));
}

function transformServiceBreakdown(insights) {
  return Object.entries(insights || {}).map(([service, data], index) => ({
    id: service || `service-${index}`,
    label: service || "Unknown",
    cost: Number(data.total_estimated_monthly_waste_usd || 0),
    tone: wasteTone(service),
  }));
}

function transformAnomalies(items) {
  return (Array.isArray(items) ? items : []).map((item) => ({
    id: item.id,
    score: Number(item.severity_score || 0),
    resourceId: item.resource_id,
    message: `${item.waste_type?.replace(/_/g, " ")} · ${item.service || "unknown"}`,
    detectedAt: item.analyzed_at
      ? new Date(item.analyzed_at).toLocaleString()
      : "Recently detected",
  }));
}

function transformGeneratedRecommendation(item) {
  let modelOutput = {};
  const explanationText = item.explanation || item.summary || item.rationale || "";
  if (typeof explanationText === "string") {
    try {
      const parsed = JSON.parse(explanationText);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) modelOutput = parsed;
    } catch {
      // Plain-text explanations are already display-ready.
    }
  }

  const resourceId = item.resource_id || item.service || "Cloud resource";
  const nestedAction = modelOutput.suggested_action;
  const topLevelAction = item.suggested_action || item.action;
  return {
    id: item.id,
    resourceId,
    resourceType: item.service || item.source_type || "resource",
    priority: item.priority || "medium",
    suggestedAction: nestedAction || (topLevelAction !== "manual_review" && topLevelAction) || "Review this resource",
    rootCause: modelOutput.explanation || explanationText || "No explanation was provided.",
    dollarSavings: Number(modelOutput.dollar_savings ?? item.dollar_savings ?? item.estimated_savings_usd ?? 0),
    carbonSavingsKg: Number(item.carbon_savings_kg || 0),
    confidence: Number(modelOutput.confidence ?? item.confidence_score ?? 0),
    status: item.status || "pending",
    environment: item.environment || "unknown",
    icon: wasteIcon(item.service || item.source_type),
    tone: wasteTone(item.service || item.source_type),
  };
}

function remediationRole(role) {
  const normalized = String(role || "").toLowerCase();
  return normalized === "admin" || normalized === "approver" ? normalized : "viewer";
}

function transformConnectedAccounts(accounts) {
  return (Array.isArray(accounts) ? accounts : []).map((account) => ({
    id: account.id,
    name: account.name,
    provider: account.provider || account.name,
    lastSync: account.lastSync
      ? new Date(account.lastSync).toLocaleString()
      : "not synced",
    status: account.status === "connected" ? "connected" : "pending",
  }));
}

function transformGreenOpsSummary(summary) {
  const carbonSavedKg = Number(summary.total_estimated_monthly_waste_usd || 0) * 0.05;
  return {
    carbonSavedKg,
    energyUsageKwh: Math.round(carbonSavedKg * 2),
    sustainabilityScore: Math.max(0, Math.round(100 - Number(summary.avg_severity_score || 0) * 100)),
    esgSummary: `${summary.total_waste_items || 0} waste items represent an estimated ${formatUsd(summary.total_estimated_monthly_waste_usd || 0)} in monthly savings potential.`,
  };
}

function transformCurrentUser(data) {
  const name = data.user?.fullName || data.user?.name || "User";
  const initials = name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return {
    user: {
      name,
      initials,
      role: data.user?.role || "Platform Eng",
      email: data.user?.email || "",
    },
    account: {
      name: data.account?.name || "workspace",
      provider: "AWS",
    },
  };
}

export const api = {
  loadDemoData: async () => {
    const orgId = encodeURIComponent(requireOrgId());
    const ingestion = await fetchAPI(`${BASE_URL}/ingest?org_id=${orgId}`, { method: "POST" });
    await fetchAPI(`${BASE_URL}/waste-analytics/analyze?org_id=${orgId}`, { method: "POST" });
    return ingestion;
  },

  getStatCards: () =>
    withFallback(async () => {
      const stats = await fetchAPI(
        `${BASE_URL}/waste-analytics/dashboard/stats?org_id=${requireOrgId()}`
      );
      return transformStatCards(stats);
    }, statCards),

  getCostTrend: (days = 30) =>
    withFallback(async () => {
      const trends = await fetchAPI(
        `${BASE_URL}/waste-analytics/analytics/cost-trend?org_id=${requireOrgId()}&days=${days}`
      );
      return transformCostTrend(trends);
    }, costTrend),

  getAttentionItems: () =>
    withFallback(async () => {
      const items = await fetchAPI(
        `${BASE_URL}/waste-analytics/items?org_id=${requireOrgId()}&min_severity=0.5&limit=5`
      );
      return transformAttentionItems(items);
    }, attentionItems),

  getRemediationHistory: () =>
    withFallback(async () => {
      const actions = await fetchAPI(
        `${BASE_URL}/waste-analytics/recommendations/history?org_id=${requireOrgId()}&limit=10`
      );
      return transformRemediationHistory(actions);
    }, remediationHistory),

  getAiInsight: () =>
    withFallback(async () => {
      const summary = await fetchAPI(
        `${BASE_URL}/waste-analytics/summary?org_id=${requireOrgId()}`
      );
      if (!summary.total_waste_items) {
        return {
          title: "Getting started",
          body: "Connect your cloud account to ingest billing data and discover optimization opportunities.",
          cta: "Ask the assistant",
        };
      }
      return {
        title: "AI Insight",
        body: `We identified ${summary.total_waste_items} waste items totaling ${formatUsd(summary.total_estimated_monthly_waste_usd)}/mo in potential savings across your infrastructure.`,
        cta: "Ask the assistant",
      };
    }, aiInsight),

  getOptimizationProgress: () =>
    withFallback(async () => {
      return fetchAPI(`${BASE_URL}/waste-analytics/greenops/progress?org_id=${requireOrgId()}`);
    }, optimizationProgress),

  getWasteByCategory: () =>
    withFallback(async () => {
      const insights = await fetchAPI(
        `${BASE_URL}/waste-analytics/insights/by-service?org_id=${requireOrgId()}`
      );
      return transformWasteByCategory(insights);
    }, wasteByCategory),

  getCurrentUser: () =>
    withFallback(async () => {
      const user_id = localStorage.getItem("user_id");
      if (!user_id) throw new Error("Not authenticated");
      const data = await fetchAPI(`${BASE_URL}/auth/me?user_id=${user_id}`);
      return transformCurrentUser(data);
    }, { user: currentUser, account: currentAccount }),

  getCloudProviders: () =>
    withFallback(async () => {
      const providers = await fetchAPI(`${BASE_URL}/auth/cloud-providers`);
      return transformCloudProviders(providers);
    }, cloudProviders),

  getIamPolicySnippet: (provider = "aws") =>
    withFallback(async () => {
      const policy = await fetchAPI(`${BASE_URL}/auth/onboarding/iam-policy?provider=${provider}`);
      return JSON.stringify(policy, null, 2);
    }, iamPolicyJson),

  getAccessChecklist: (provider = "aws") =>
    withFallback(async () => {
      const items = await fetchAPI(
        `${BASE_URL}/auth/onboarding/access-checklist?provider=${provider}`
      );
      return transformAccessChecklist(items);
    }, accessChecklist),

  login: async (email, password) => {
    try {
      const response = await fetchAPI(`${BASE_URL}/auth/login`, {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });

      if (response.access_token) localStorage.setItem("auth_token", response.access_token);
      if (response.user_id) localStorage.setItem("user_id", response.user_id);
      if (response.org_id) localStorage.setItem("org_id", response.org_id);

      return { ok: true, ...response };
    } catch (e) {
      console.error("Login failed:", e);
      return { ok: false, error: e.message };
    }
  },

  signup: async (email, password, org_name, full_name) => {
    try {
      const response = await fetchAPI(`${BASE_URL}/auth/signup`, {
        method: "POST",
        body: JSON.stringify({ email, password, org_name, full_name }),
      });

      if (response.access_token) localStorage.setItem("auth_token", response.access_token);
      if (response.user_id) localStorage.setItem("user_id", response.user_id);
      if (response.org_id) localStorage.setItem("org_id", response.org_id);

      return { ok: true, ...response };
    } catch (e) {
      console.error("Signup failed:", e);
      return { ok: false, error: e.message };
    }
  },

  connectCloud: async (provider, credentials = {}) => {
    try {
      const org_id = requireOrgId();
      const response = await fetchAPI(
        `${BASE_URL}/auth/onboarding/connect?provider=${provider}&org_id=${org_id}`,
        {
          method: "POST",
          body: JSON.stringify({ provider, credentials }),
        }
      );
      return { ok: true, ...response };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  },

  ingestAndAnalyze: async () => {
    try {
      const org_id = requireOrgId();
      await fetchAPI(`${BASE_URL}/ingest?org_id=${org_id}`, { method: "POST" });
      await fetchAPI(`${BASE_URL}/waste-analytics/analyze?org_id=${org_id}`, { method: "POST" });
      return { ok: true };
    } catch (e) {
      console.error("Ingest/analyze failed:", e);
      return { ok: false, error: e.message };
    }
  },

  logout: () => {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("user_id");
    localStorage.removeItem("org_id");
  },

  isAuthenticated: () => !!localStorage.getItem("org_id"),

  setAuthToken: (token) => {
    localStorage.setItem("auth_token", token);
  },

  getAuthToken,

  getServiceBreakdown: () =>
    withFallback(async () => {
      const insights = await fetchAPI(
        `${BASE_URL}/waste-analytics/insights/by-service?org_id=${requireOrgId()}`
      );
      return transformServiceBreakdown(insights);
    }, serviceBreakdown),

  getAnomalies: () =>
    withFallback(async () => {
      const items = await fetchAPI(
        `${BASE_URL}/waste-analytics/items?org_id=${requireOrgId()}&min_severity=0.6&limit=10`
      );
      return transformAnomalies(items);
    }, anomalies),

  getForecastAccuracy: () =>
    withFallback(async () => {
      const metrics = await fetchAPI(
        `${BASE_URL}/waste-analytics/forecast-accuracy?org_id=${requireOrgId()}`
      );
      return {
        mape: Number(metrics.mape || 0),
        precision: Number(metrics.precision || 0),
        recall: Number(metrics.recall || 0),
        accuracy: Number(metrics.accuracy || 0),
        trend: metrics.trend || "stable",
      };
    }, forecastAccuracy),

  getRecommendations: async (filters = {}) => {
      const org_id = requireOrgId();
      const query = new URLSearchParams({ org_id, limit: "50" });
      if (filters.service) query.set("service", filters.service);
      if (filters.environment) query.set("environment", filters.environment);
      const items = await fetchAPI(`${BASE_URL}/recommendations?${query}`);
      return items.map(transformGeneratedRecommendation);
  },

  generateRecommendations: async (limit = 5, question) => {
    const response = await fetchAPI(`${BASE_URL}/recommendations/generate`, {
      method: "POST",
      body: JSON.stringify({ org_id: requireOrgId(), limit, ...(question && { question }) }),
    });
    return (response.recommendations || []).map(transformGeneratedRecommendation);
  },

  prepareAutomationPlan: (recommendationIds, userRole) =>
    fetchAPI(`${BASE_URL}/remediation/plan`, {
      method: "POST",
      body: JSON.stringify({
        org_id: requireOrgId(),
        recommendation_ids: recommendationIds,
        user_role: remediationRole(userRole),
      }),
    }),

  getAutomationPlans: async () => {
    const query = new URLSearchParams({ org_id: requireOrgId(), limit: "100" });
    const response = await fetchAPI(`${BASE_URL}/remediation/history?${query}`);
    return response.plans || [];
  },

  dismissRecommendation: async (id) => {
    const org_id = requireOrgId();
    return fetchAPI(`${BASE_URL}/recommendations/${id}/dismiss`, {
      method: "POST",
      body: JSON.stringify({ org_id }),
    });
  },

  processRemediation: async (recommendationIds, userRole) =>
    fetchAPI(`${BASE_URL}/remediation/process`, {
      method: "POST",
      body: JSON.stringify({
        org_id: requireOrgId(),
        recommendation_ids: recommendationIds,
        user_role: remediationRole(userRole),
        dry_run: true,
      }),
    }),

  approveRemediation: async (recommendationIds, userRole, dryRun = true, confirmations = {}) =>
    fetchAPI(`${BASE_URL}/remediation/approve`, {
      method: "POST",
      body: JSON.stringify({
        org_id: requireOrgId(),
        recommendation_ids: recommendationIds,
        user_role: remediationRole(userRole),
        dry_run: dryRun,
        confirmations,
      }),
    }),

  askAssistant: async (question, history = []) =>
    fetchAPI(`${BASE_URL}/assistant/chat`, {
      method: "POST",
      body: JSON.stringify({ org_id: requireOrgId(), question, history }),
    }),

  updateRecommendationStatus: async (id, status) => {
    const org_id = requireOrgId();
    return fetchAPI(`${BASE_URL}/waste-analytics/recommendations/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status, org_id }),
    });
  },

  getAlerts: () =>
    withFallback(async () => {
      const items = await fetchAPI(
        `${BASE_URL}/waste-analytics/items?org_id=${requireOrgId()}&min_severity=0.8&limit=20`
      );
      return transformAnomalies(items).map((item) => ({
        id: item.id,
        type: "anomaly",
        severity: item.score >= 0.9 ? "critical" : "warning",
        message: `${item.resourceId}: ${item.message}`,
        channel: "email",
        sentAt: item.detectedAt,
      }));
    }, alerts),

  getGreenOpsSummary: () =>
    withFallback(async () => {
      const summary = await fetchAPI(
        `${BASE_URL}/waste-analytics/summary?org_id=${requireOrgId()}`
      );
      return transformGreenOpsSummary(summary);
    }, greenOpsSummary),

  getEsgBreakdown: () =>
    withFallback(async () => {
      const insights = await fetchAPI(
        `${BASE_URL}/waste-analytics/insights/by-environment?org_id=${requireOrgId()}`
      );
      const total =
        Object.values(insights || {}).reduce(
          (sum, item) => sum + Number(item.total_estimated_monthly_waste_usd || 0),
          0
        ) || 1;
      return Object.entries(insights || {}).map(([environment, item], index) => ({
        id: environment || `environment-${index}`,
        label: environment || "Unknown",
        pct: Math.round((Number(item.total_estimated_monthly_waste_usd || 0) / total) * 100),
        tone: wasteTone(environment),
      }));
    }, esgBreakdown),

  getConnectedAccounts: () =>
    withFallback(async () => {
      const accounts = await fetchAPI(
        `${BASE_URL}/auth/connected-accounts?org_id=${requireOrgId()}`
      );
      return transformConnectedAccounts(accounts);
    }, connectedAccounts),

  getNotificationSettings: () => {
    const raw = localStorage.getItem("notification_settings");
    if (raw) {
      try {
        return Promise.resolve(JSON.parse(raw));
      } catch {
        /* fall through */
      }
    }
    return mockResolve({ types: notificationSettings, channels: notificationChannels });
  },

  updateNotificationSetting: (id, enabled) => {
    const raw = localStorage.getItem("notification_settings");
    let settings = { types: notificationSettings, channels: notificationChannels };
    if (raw) {
      try {
        settings = JSON.parse(raw);
      } catch {
        /* keep defaults */
      }
    }
    settings.types = (settings.types || []).map((t) => (t.id === id ? { ...t, enabled } : t));
    settings.channels = (settings.channels || []).map((c) => (c.id === id ? { ...c, enabled } : c));
    localStorage.setItem("notification_settings", JSON.stringify(settings));
    return Promise.resolve({ id, enabled });
  },
};


export { BASE_URL };
