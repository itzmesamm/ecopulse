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

function recommendationStatus(backendStatus) {
  if (backendStatus === "completed" || backendStatus === "executed" || backendStatus === "approved") {
    return "executed";
  }
  if (backendStatus === "failed" || backendStatus === "rejected" || backendStatus === "dismissed") {
    return "rejected";
  }
  return "pending";
}

function transformRecommendations(items, history = []) {
  const statusByItem = {};
  (Array.isArray(history) ? history : []).forEach((action) => {
    if (action.waste_item_id) {
      statusByItem[action.waste_item_id] = recommendationStatus(action.status);
    }
  });

  return (Array.isArray(items) ? items : []).map((item) => {
    const severity = Number(item.severity_score || 0);
    return {
      id: item.id,
      resourceId: item.resource_id,
      resourceType: item.service || "resource",
      priority: severity >= 0.8 ? "high" : severity >= 0.6 ? "medium" : "low",
      suggestedAction: `Optimize ${item.service || "resource"}`,
      rootCause: item.details || item.waste_type?.replace(/_/g, " ") || "Potential cloud waste detected.",
      dollarSavings: Number(item.estimated_monthly_waste_usd || 0),
      carbonSavingsKg: Math.round(Number(item.estimated_monthly_waste_usd || 0) * 0.05 * 100) / 100,
      confidence: severity,
      status: statusByItem[item.id] || "pending",
      icon: wasteIcon(item.service),
      tone: wasteTone(item.service),
      analyzedAt: item.analyzed_at ? new Date(item.analyzed_at).getTime() : 0,
    };
  });
}

function transformAiRecommendations(items) {
  return (Array.isArray(items) ? items : []).map((item) => {
    const priority = String(item.priority || "medium").toLowerCase();
    const confidence = Number(item.confidence_score ?? 0);
    return {
      id: item.id,
      resourceId: item.resource_id || item.title || "resource",
      resourceType: item.service || item.source_type || "resource",
      priority: ["high", "medium", "low"].includes(priority) ? priority : "medium",
      suggestedAction: item.suggested_action || item.action || item.title || "Review optimization",
      rootCause:
        item.explanation ||
        item.rationale ||
        item.summary ||
        "AI recommendation grounded in waste and operational signals.",
      dollarSavings: Number(item.dollar_savings ?? item.estimated_savings_usd ?? 0),
      carbonSavingsKg: Math.round(Number(item.carbon_savings_kg ?? 0) * 100) / 100,
      confidence: confidence > 1 ? confidence / 100 : confidence,
      status: recommendationStatus(item.status),
      icon: wasteIcon(item.service),
      tone: wasteTone(item.service),
      analyzedAt: item.created_at ? new Date(item.created_at).getTime() : 0,
    };
  });
}

function transformAlertRows(rows) {
  return (Array.isArray(rows) ? rows : []).map((row) => ({
    id: row.id,
    type: row.alert_type || "anomaly",
    severity: String(row.severity || "warning").toLowerCase(),
    message: row.message || "Alert",
    channel: row.channel || "in-app",
    sentAt: row.sent_at ? new Date(row.sent_at).toLocaleString() : "Recently",
  }));
}

function transformGreenOpsReport(report) {
  return {
    carbonSavedKg: Number(report.total_carbon_savings_kg || 0),
    energyUsageKwh: Number(report.estimated_energy_kwh_saved || 0),
    sustainabilityScore: Math.round(Number(report.sustainability_score || 0)),
    esgSummary:
      report.esg_summary ||
      `${report.executed_recommendations_count || 0} executed recommendations saved ${formatUsd(report.total_dollar_savings_usd || 0)}.`,
  };
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
      const org_id = requireOrgId();
      const [summary, recs] = await Promise.all([
        fetchAPI(`${BASE_URL}/waste-analytics/summary?org_id=${org_id}`),
        fetchAPI(`${BASE_URL}/recommendations?org_id=${org_id}&limit=3`).catch(() => []),
      ]);
      if (Array.isArray(recs) && recs.length > 0) {
        const top = recs[0];
        const savings = Number(top.dollar_savings ?? top.estimated_savings_usd ?? 0);
        return {
          title: top.title || "AI Recommendation",
          body:
            top.summary ||
            top.explanation ||
            `Top action: ${top.suggested_action || top.action}. Estimated savings ${formatUsd(savings)}/mo.`,
          cta: "Review recommendations",
        };
      }
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

  demoLogin: async () => {
    try {
      const response = await fetchAPI(`${BASE_URL}/auth/dev-login`, { method: "POST" });
      if (response.access_token) localStorage.setItem("auth_token", response.access_token);
      if (response.user_id) localStorage.setItem("user_id", response.user_id);
      if (response.org_id) localStorage.setItem("org_id", response.org_id);
      return { ok: true, ...response };
    } catch (e) {
      console.error("Demo login failed:", e);
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
      console.error("Cloud connection failed:", e);
      return { ok: false, error: e.message };
    }
  },

  ingestAndAnalyze: async () => {
    try {
      const org_id = requireOrgId();
      const pipeline = await fetchAPI(`${BASE_URL}/pipeline/run`, {
        method: "POST",
        body: JSON.stringify({ org_id, collect: true }),
      });
      return { ok: true, pipeline };
    } catch (e) {
      console.error("Pipeline run failed:", e);
      return { ok: false, error: e.message };
    }
  },

  logout: () => {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("user_id");
    localStorage.removeItem("org_id");
  },

  isAuthenticated: () => !!localStorage.getItem("org_id") && !!localStorage.getItem("auth_token"),

  setAuthToken: (token) => {
    localStorage.setItem("auth_token", token);
  },

  getAuthToken,

  askAssistant: async (question, history = []) => {
    const org_id = requireOrgId();
    return fetchAPI(`${BASE_URL}/assistant/chat`, {
      method: "POST",
      body: JSON.stringify({ org_id, question, history }),
    });
  },

  getServiceBreakdown: () =>
    withFallback(async () => {
      const insights = await fetchAPI(
        `${BASE_URL}/waste-analytics/insights/by-service?org_id=${requireOrgId()}`
      );
      return transformServiceBreakdown(insights);
    }, serviceBreakdown),

  getAnomalies: () =>
    withFallback(async () => {
      try {
        const findings = await fetchAPI(
          `${BASE_URL}/anomalies/detect?org_id=${requireOrgId()}`
        );
        if (Array.isArray(findings) && findings.length > 0) {
          return findings.map((item, index) => ({
            id: `${item.resource_id}-${index}`,
            score: Number(item.severity_score || item.anomaly_score || 0),
            resourceId: item.resource_id,
            message: item.details || `${item.service || "resource"} anomaly`,
            detectedAt: "Just now",
          }));
        }
      } catch (e) {
        console.warn("Anomaly detect failed, falling back to waste items:", e.message);
      }
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

  getRecommendations: (filters = {}) =>
    withFallback(async () => {
      const org_id = requireOrgId();
      let rows = await fetchAPI(`${BASE_URL}/recommendations?org_id=${org_id}&limit=20`);
      if (!Array.isArray(rows) || rows.length === 0) {
        await fetchAPI(`${BASE_URL}/recommendations/generate`, {
          method: "POST",
          body: JSON.stringify({ org_id, limit: 5 }),
        }).catch(() => null);
        rows = await fetchAPI(`${BASE_URL}/recommendations?org_id=${org_id}&limit=20`);
      }
      let mapped = transformAiRecommendations(rows);
      if (filters.priority && filters.priority !== "all") {
        mapped = mapped.filter((item) => item.priority === filters.priority);
      }
      if (filters.resourceType && filters.resourceType !== "all") {
        mapped = mapped.filter((item) => item.resourceType === filters.resourceType);
      }
      return mapped;
    }, recommendations),

  updateRecommendationStatus: async (id, status) => {
    const org_id = requireOrgId();
    return fetchAPI(`${BASE_URL}/recommendations/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status, org_id }),
    });
  },

  getAlerts: () =>
    withFallback(async () => {
      const org_id = requireOrgId();
      await fetchAPI(`${BASE_URL}/alerts/check`, {
        method: "POST",
        body: JSON.stringify({ org_id }),
      }).catch(() => null);
      const rows = await fetchAPI(`${BASE_URL}/alerts?org_id=${org_id}&limit=50`);
      const mapped = transformAlertRows(rows);
      if (mapped.length > 0) return mapped;
      const items = await fetchAPI(
        `${BASE_URL}/waste-analytics/items?org_id=${org_id}&min_severity=0.8&limit=20`
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
      try {
        const report = await fetchAPI(`${BASE_URL}/greenops/report?org_id=${requireOrgId()}`);
        return transformGreenOpsReport(report);
      } catch (e) {
        console.warn("GreenOps report failed, using waste summary:", e.message);
        const summary = await fetchAPI(
          `${BASE_URL}/waste-analytics/summary?org_id=${requireOrgId()}`
        );
        return transformGreenOpsSummary(summary);
      }
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
