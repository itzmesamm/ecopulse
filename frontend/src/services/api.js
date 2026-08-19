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
   recommendations,
   alerts,
   greenOpsSummary,
   esgBreakdown,
   connectedAccounts,
   notificationSettings,
   notificationChannels,
 } from "../data/mockData";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const MOCK_LATENCY_MS = 260;
const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA !== "false";

function mockResolve(payload) {
  return new Promise((resolve) => setTimeout(() => resolve(payload), MOCK_LATENCY_MS));
}

function getAuthToken() {
  return localStorage.getItem("auth_token");
}

function getOrgId() {
  return localStorage.getItem("org_id");
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
  try {
    return await fetcher();
  } catch (e) {
    console.warn("API call failed, using mock data:", e.message);
    return mockResolve(fallback);
  }
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
    return { currentLabel: "$0", actual: [], forecast: [] };
  }

  const costs = trends.map((t) => t.cost);
  const split = Math.max(1, Math.floor(costs.length * 0.7));
  const actual = costs.slice(0, split);
  const lastActual = actual[actual.length - 1] || 0;
  const forecast = costs.slice(split);
  if (forecast.length === 0) {
    forecast.push(lastActual * 0.9, lastActual * 0.85, lastActual * 0.8);
  }

  return {
    currentLabel: formatUsd(lastActual),
    actual,
    forecast,
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
    };
  });
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
  getStatCards: () =>
    withFallback(async () => {
      const org_id = getOrgId();
      const stats = await fetchAPI(`${BASE_URL}/waste-analytics/dashboard/stats?org_id=${org_id}`);
      return transformStatCards(stats);
    }, statCards),

  getCostTrend: () =>
    withFallback(async () => {
      const org_id = getOrgId();
      const trends = await fetchAPI(
        `${BASE_URL}/waste-analytics/analytics/cost-trend?org_id=${org_id}&days=30`
      );
      return transformCostTrend(trends);
    }, costTrend),

  getAttentionItems: () =>
    withFallback(async () => {
      const org_id = getOrgId();
      const items = await fetchAPI(
        `${BASE_URL}/waste-analytics/items?org_id=${org_id}&min_severity=0.5&limit=5`
      );
      return transformAttentionItems(items);
    }, attentionItems),

  getRemediationHistory: () =>
    withFallback(async () => {
      const org_id = getOrgId();
      const actions = await fetchAPI(
        `${BASE_URL}/waste-analytics/recommendations/history?org_id=${org_id}&limit=10`
      );
      return transformRemediationHistory(actions);
    }, remediationHistory),

  getAiInsight: () =>
    withFallback(async () => {
      const org_id = getOrgId();
      const summary = await fetchAPI(`${BASE_URL}/waste-analytics/summary?org_id=${org_id}`);
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
      const org_id = getOrgId();
      const progress = await fetchAPI(
        `${BASE_URL}/waste-analytics/greenops/progress?org_id=${org_id}`
      );
      return progress;
    }, optimizationProgress),

  getWasteByCategory: () =>
    withFallback(async () => {
      const org_id = getOrgId();
      const insights = await fetchAPI(
        `${BASE_URL}/waste-analytics/insights/by-service?org_id=${org_id}`
      );
      return transformWasteByCategory(insights);
    }, wasteByCategory),

  getCurrentUser: () =>
    withFallback(async () => {
      const user_id = localStorage.getItem("user_id");
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

      if (response.access_token) {
        localStorage.setItem("auth_token", response.access_token);
        localStorage.setItem("user_id", response.user_id);
        localStorage.setItem("org_id", response.org_id);
      }

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

      if (response.user_id && response.org_id) {
        localStorage.setItem("user_id", response.user_id);
        localStorage.setItem("org_id", response.org_id);
      }

      return { ok: true, ...response };
    } catch (e) {
      console.error("Signup failed:", e);
      return { ok: false, error: e.message };
    }
  },

  connectCloud: async (provider, credentials = {}) => {
    try {
      const org_id = getOrgId();
      const response = await fetchAPI(
        `${BASE_URL}/auth/onboarding/connect?provider=${provider}&org_id=${org_id}`,
        {
          method: "POST",
          body: JSON.stringify({ provider, credentials }),
        }
      );
      return { ok: true, ...response };
    } catch (e) {
      console.error("Cloud connection failed:", e);
      return { ok: false, error: e.message };
    }
  },

  ingestAndAnalyze: async () => {
    try {
      const org_id = getOrgId();
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
    // GET /api/analytics/service-breakdown
  getServiceBreakdown: () => mockResolve(serviceBreakdown),

  // GET /api/analytics/anomalies
  getAnomalies: () => mockResolve(anomalies),

  // GET /api/analytics/forecast-accuracy
  getForecastAccuracy: () => mockResolve(forecastAccuracy),

  // GET /api/recommendations
  getRecommendations: () => mockResolve(recommendations),

  // POST /api/recommendations/:id/approve | /reject
  updateRecommendationStatus: (id, status) => mockResolve({ id, status }),

  // GET /api/alerts
  getAlerts: () => mockResolve(alerts),

  // GET /api/greenops/summary
  getGreenOpsSummary: () => mockResolve(greenOpsSummary),

  // GET /api/greenops/breakdown
  getEsgBreakdown: () => mockResolve(esgBreakdown),

  // GET /api/settings/accounts
  getConnectedAccounts: () => mockResolve(connectedAccounts),

  // GET /api/settings/notifications
  getNotificationSettings: () => mockResolve({ types: notificationSettings, channels: notificationChannels }),

  // POST /api/settings/notifications
  updateNotificationSetting: (id, enabled) => mockResolve({ id, enabled }),
};

export { BASE_URL };
