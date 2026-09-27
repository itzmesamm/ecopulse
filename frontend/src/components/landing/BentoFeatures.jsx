import { IconBadge } from "../ui/Pill";

const FEATURES = [
  {
    icon: "database",
    tone: "blue",
    title: "Unified ingestion",
    desc: "Billing APIs, infra metrics, GPU telemetry, Kubernetes and logs — normalized into one clean data layer.",
  },
  {
    icon: "analytics",
    tone: "purple",
    title: "Waste & forecast analytics",
    desc: "Idle-resource detection, anomaly scoring, and 30/60/90-day cost forecasting out of the box.",
  },
  {
    icon: "insights",
    tone: "teal",
    title: "GenAI recommendations",
    desc: "Grounded, RAG-backed explanations of root cause, cost impact, and the exact fix to apply.",
  },
];

export default function BentoFeatures() {
  return (
    <section className="bento">
      <h2>Every layer of FinOps, in one platform</h2>
      <p className="sub">From raw telemetry to autonomous remediation — nothing bolted on.</p>

      <div className="bento-grid">
        {FEATURES.map((f) => (
          <div className="card bento-card" key={f.title}>
            <IconBadge icon={f.icon} tone={f.tone} />
            <h3>{f.title}</h3>
            <p>{f.desc}</p>
          </div>
        ))}
      </div>

      <div className="dual-bento">
        <div className="card dual-card orange">
          <span className="lbl">Average savings</span>
          <span className="num display">31%</span>
          <p>Median reduction in monthly cloud spend within the first 60 days.</p>
        </div>
        <div className="card dual-card teal">
          <span className="lbl">Carbon reduced</span>
          <span className="num display">2.4t</span>
          <p>Average CO₂ saved per team per month once auto-remediation is on.</p>
        </div>
      </div>
    </section>
  );
}
