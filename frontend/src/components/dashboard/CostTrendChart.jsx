import { useMemo } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  CartesianGrid,
} from "recharts";

const MONTHS = ["Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export default function CostTrendChart({ data }) {
  const chartData = useMemo(() => {
    if (!data) return [];
    const { actual = [], forecast = [], labels = [] } = data;
    const points = actual.map((v, i) => ({
      month: labels[i] || MONTHS[i] || `M${i}`,
      actual: v,
      forecast: null,
    }));

    if (points.length) points[points.length - 1].forecast = points[points.length - 1].actual;

    forecast.forEach((v, i) => {
      const idx = actual.length + i;
      points.push({
        month: labels[idx] || MONTHS[idx] || `F${i + 1}`,
        actual: null,
        forecast: v,
      });
    });

    return points;
  }, [data]);

  return (
    <div className="chart-wrap">
      {data && <div className="chart-floating-val">{data.currentLabel}</div>}
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 30, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="actualFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--orange)" stopOpacity={0.35} />
              <stop offset="100%" stopColor="var(--orange)" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="forecastFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--teal)" stopOpacity={0.25} />
              <stop offset="100%" stopColor="var(--teal)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
          <XAxis
            dataKey="month"
            axisLine={false}
            tickLine={false}
            tick={{ fill: "var(--text-3)", fontSize: 11 }}
          />
          <YAxis hide domain={["dataMin - 10", "dataMax + 20"]} />
          <Tooltip
            contentStyle={{
              background: "var(--surface)",
              border: "1px solid var(--card-border)",
              borderRadius: 12,
              fontSize: 12,
              color: "var(--text)",
            }}
            labelStyle={{ color: "var(--text-2)" }}
          />
          <Area
            type="monotone"
            dataKey="actual"
            stroke="var(--orange)"
            strokeWidth={2.5}
            fill="url(#actualFill)"
            connectNulls
            dot={false}
          />
          <Area
            type="monotone"
            dataKey="forecast"
            stroke="var(--teal)"
            strokeWidth={2.5}
            strokeDasharray="5 5"
            fill="url(#forecastFill)"
            connectNulls
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
