import { useNavigate } from "react-router-dom";
import { AreaChart, Area, ResponsiveContainer } from "recharts";
import { Icon } from "../ui/Icon";

const MINI_DATA = [
  { v: 150 }, { v: 120 }, { v: 160 }, { v: 130 }, { v: 100 },
  { v: 140 }, { v: 110 }, { v: 80 }, { v: 60 }, { v: 45 }, { v: 30 },
];

export default function Hero() {
  const navigate = useNavigate();

  return (
    <section className="hero">
      <div>
        <div className="eyebrow">
          <span className="dot" /> AI-powered FinOps &amp; GreenOps
        </div>
        <h1>
          Stop cloud waste <span className="hl-orange">before</span> it hits
          your bill. Cut <span className="hl-teal">carbon</span> while you're at it.
        </h1>
        <p>
          Veya watches your billing, compute, and Kubernetes usage in real
          time, tells you exactly what's being wasted, and can fix it
          automatically — with every action logged and reversible.
        </p>
        <div className="ctas">
          <button type="button" className="btn btn-primary" onClick={() => navigate("/signup")}>
            Start free trial
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => navigate("/login")}>
            Sign in
          </button>
        </div>
      </div>

      <div className="hero-visual">
        <div className="card hero-card">
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <div style={{ fontSize: 13, color: "var(--text-2)", fontWeight: 600 }}>
              Monthly cloud cost
            </div>
            <div className="pill teal">
              <Icon name="down" /> 24% since onboarding
            </div>
          </div>
          <div style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 30, marginBottom: 6 }}>
            $38,240
          </div>
          <div className="hero-chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={MINI_DATA} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="heroFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--orange)" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="var(--orange)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area
                  type="monotone"
                  dataKey="v"
                  stroke="var(--orange)"
                  strokeWidth={2.5}
                  fill="url(#heroFill)"
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="finding-float">
            <div className="icon-badge orange">
              <Icon name="server" />
            </div>
            <div style={{ flex: 1 }}>
              <span className="tag">Waste finding</span>
              <div className="title">gpu-04 idle for 36 hours</div>
            </div>
            <div className="cost">$310/mo</div>
          </div>
        </div>
      </div>
    </section>
  );
}
