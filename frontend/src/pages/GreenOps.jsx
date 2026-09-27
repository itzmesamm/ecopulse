import { useEffect, useState } from "react";
import AppShell from "../components/layout/AppShell";
import Topbar from "../components/layout/Topbar";
import CarbonSummary from "../components/greenops/CarbonSummary";
import EsgBreakdown from "../components/greenops/EsgBreakdown";
import { api } from "../services/api";

export default function GreenOps() {
  const [summary, setSummary] = useState(null);
  const [breakdown, setBreakdown] = useState([]);

  useEffect(() => {
    api.getGreenOpsSummary().then(setSummary);
    api.getEsgBreakdown().then(setBreakdown);
  }, []);

  return (
    <AppShell>
      <Topbar title="GreenOps Reports" />
      <div className="page-sub">CO₂ impact, energy usage, and sustainability score from executed remediations.</div>

      {summary && <CarbonSummary summary={summary} />}

      <div style={{ marginTop: 16 }}>
        {breakdown.length > 0 && <EsgBreakdown categories={breakdown} />}
      </div>

      {summary && (
        <div className="card esg-summary-card">
          <h3>ESG summary</h3>
          <p>{summary.esgSummary}</p>
        </div>
      )}
    </AppShell>
  );
}