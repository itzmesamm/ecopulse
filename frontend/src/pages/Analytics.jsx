import { useEffect, useState } from "react";
import AppShell from "../components/layout/AppShell";
import Topbar from "../components/layout/Topbar";
import CostTrendChart from "../components/dashboard/CostTrendChart";
import WasteByCategory from "../components/dashboard/WasteByCategory";
import ServiceBreakdownChart from "../components/analytics/ServiceBreakdownChart";
import AnomalyList from "../components/analytics/AnomalyList";
import ForecastAccuracy from "../components/analytics/ForecastAccuracy";
import { api } from "../services/api";

export default function Analytics() {
  const [trend, setTrend] = useState(null);
  const [services, setServices] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [waste, setWaste] = useState([]);
  const [accuracy, setAccuracy] = useState(null);

  useEffect(() => {
    api.getCostTrend().then(setTrend);
    api.getServiceBreakdown().then(setServices);
    api.getAnomalies().then(setAnomalies);
    api.getWasteByCategory().then(setWaste);
    api.getForecastAccuracy().then(setAccuracy);
  }, []);

  return (
    <AppShell>
      <Topbar title="Analytics" />
      <div className="page-sub">Cost trends, waste analytics, and anomaly detection across your connected accounts.</div>

      <div className="card panel" style={{ marginBottom: 16 }}>
        <div className="panel-head">
          <h3>Cost trend &amp; forecast</h3>
        </div>
        <CostTrendChart data={trend} />
      </div>

      <div className="two-col">
        {services.length > 0 && <ServiceBreakdownChart services={services} />}
        {waste.length > 0 && <WasteByCategory categories={waste} />}
      </div>

      <div className="two-col">
        {anomalies.length > 0 && <AnomalyList anomalies={anomalies} />}
        {accuracy && <ForecastAccuracy metrics={accuracy} />}
      </div>
    </AppShell>
  );
}
