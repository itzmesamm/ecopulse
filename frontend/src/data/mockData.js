// Mock data fixtures. Shapes mirror what /backend/app/api endpoints
// (billing.py, gpu.py, recommendations.py, reports.py, ...) are expected
// to return, so swapping mockApi for a real fetch layer is a drop-in change.

export const currentUser = {
  name: "Nikita M.",
  initials: "NM",
  role: "Platform Eng",
  email: "nikita@meridian.io",
};

export const currentAccount = {
  name: "meridian-prod",
  provider: "AWS",
};

export const statCards = [
  {
    id: "monthly-cost",
    label: "Monthly cloud cost",
    value: "$42,180",
    icon: "creditCard",
    tone: "blue",
    pill: { tone: "red", direction: "down", text: "3.2% vs last month" },
  },
  {
    id: "savings-identified",
    label: "Savings identified",
    value: "$18,420",
    icon: "zap",
    tone: "orange",
    pill: { tone: "orange", direction: "up", text: "12 findings" },
  },
  {
    id: "carbon-saved",
    label: "Carbon saved",
    value: "2.1t",
    icon: "leaf",
    tone: "teal",
    pill: { tone: "teal", text: "CO\u2082 this month" },
  },
  {
    id: "needs-approval",
    label: "Needs approval",
    value: "3",
    icon: "hourglass",
    tone: "red",
    pill: { tone: "red", text: "1 overdue" },
  },
];

// Monthly cost trend, actuals then forecast (Prophet output in the real pipeline)
export const costTrend = {
  currentLabel: "$38.2k",
  actual: [150, 120, 160, 130, 100, 140, 110, 80, 120, 90, 60],
  forecast: [60, 50, 45, 38, 32, 26, 20],
};

export const attentionItems = [
  {
    id: "gpu-04",
    title: "gpu-04",
    desc: "Idle GPU \u00b7 36h",
    cost: "$310/mo",
    icon: "server",
    tone: "orange",
  },
  {
    id: "i-8f3a21bc",
    title: "i-8f3a21bc",
    desc: "Oversized \u00b7 8% CPU",
    cost: "$142/mo",
    icon: "monitor",
    tone: "blue",
  },
  {
    id: "vol-9c21",
    title: "vol-9c21",
    desc: "Unused \u00b7 14 days",
    cost: "$58/mo",
    icon: "database",
    tone: "purple",
  },
];

export const remediationHistory = [
  {
    id: "rem-1",
    title: "gpu-04 downscaled",
    sub: "Today \u00b7 2 actions",
    amount: "$310.00",
    status: "Executed",
    tone: "green",
    icon: "server",
  },
  {
    id: "rem-2",
    title: "i-8f3a21bc resize",
    sub: "Aug 12 \u00b7 pending approval",
    amount: "$142.00",
    status: "Pending",
    tone: "orange",
    icon: "monitor",
  },
  {
    id: "rem-3",
    title: "vol-9c21 deletion",
    sub: "Aug 9 \u00b7 rejected by admin",
    amount: "$58.00",
    status: "Rejected",
    tone: "red",
    icon: "database",
  },
  {
    id: "rem-4",
    title: "pod cluster rescheduled",
    sub: "Aug 7 \u00b7 sandbox auto-run",
    amount: "$96.00",
    status: "Executed",
    tone: "green",
    icon: "boxes",
  },
];

export const aiInsight = {
  title: "AI Insight",
  body: "Your GPU waste dropped 24% this month after enabling auto-remediation on sandbox resources \u2014 on pace to save an extra $2,100 next month.",
  cta: "Ask the assistant",
};

export const optimizationProgress = [
  { id: "savings", label: "Savings goal", current: 18420, target: 25000, tone: "orange" },
  { id: "carbon", label: "Carbon reduction goal", current: 2.1, target: 3, unit: "t CO\u2082", tone: "teal" },
];

export const wasteByCategory = [
  { id: "idle-gpu", label: "Idle GPU", pct: 40, tone: "orange" },
  { id: "oversized", label: "Oversized", pct: 24, tone: "blue" },
  { id: "storage", label: "Storage", pct: 20, tone: "purple" },
  { id: "k8s-pods", label: "K8s pods", pct: 16, tone: "teal" },
];

export const cloudProviders = [
  { id: "aws", name: "AWS", desc: "Cost Explorer + CloudWatch", recommended: true },
  { id: "gcp", name: "GCP", desc: "Billing export + Monitoring" },
  { id: "azure", name: "Azure", desc: "Cost Management + Monitor" },
];

export const iamPolicyJson = `{
  "Effect": "Allow",
  "Action": [
    "ce:GetCostAndUsage",
    "cloudwatch:GetMetricData"
  ],
  "Resource": "*"
}`;

export const accessChecklist = [
  { id: "billing", label: "Billing read access", status: "ok" },
  { id: "cloudwatch", label: "CloudWatch metrics read access", status: "ok" },
  { id: "k8s", label: "Kubernetes cluster access", status: "pending" },
  { id: "gpu", label: "GPU telemetry access", status: "pending" },
];

export const notificationChannels = [
  { id: "slack", label: "Slack", desc: "#finops-alerts webhook", enabled: true },
  { id: "email", label: "Email", desc: "nikita@meridian.io", enabled: true },
];