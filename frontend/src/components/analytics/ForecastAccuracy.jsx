export default function ForecastAccuracy({ metrics }) {
  return (
    <div className="card panel">
      <div className="panel-head">
        <h3>Forecast &amp; detection accuracy</h3>
      </div>
      <div className="metric-trio">
        <div className="m">
          <b>{metrics.mape}%</b>
          <span>Forecast MAPE</span>
        </div>
        <div className="m">
          <b>{metrics.precision.toFixed(2)}</b>
          <span>Waste precision</span>
        </div>
        <div className="m">
          <b>{metrics.recall.toFixed(2)}</b>
          <span>Waste recall</span>
        </div>
      </div>
    </div>
  );
}