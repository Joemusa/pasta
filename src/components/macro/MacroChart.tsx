"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MacroPoint } from "@/lib/types";
import { formatMacroPeriod, formatPct } from "@/lib/intelligence/macro-commentary";

export function MacroChart({ points }: { points: MacroPoint[] }) {
  const data = points.map((p) => ({
    period: p.period,
    inflation: p.inflation,
    policyRate: p.policyRate,
  }));

  return (
    <div className="h-[360px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#d4cec2" strokeDasharray="3 3" />
          <XAxis
            dataKey="period"
            tick={{ fill: "#6d665c", fontSize: 11 }}
            tickFormatter={(period: string) => (period.endsWith("-01") ? period.slice(0, 4) : "")}
            minTickGap={24}
          />
          <YAxis
            tick={{ fill: "#6d665c", fontSize: 11 }}
            tickFormatter={(value: number) => `${value}%`}
            width={42}
            domain={["auto", "auto"]}
          />
          <Tooltip
            contentStyle={{
              background: "#fff",
              border: "1px solid #d4cec2",
              borderRadius: 2,
              fontSize: 12,
            }}
            labelFormatter={(period) => formatMacroPeriod(String(period))}
            formatter={(value, name) => [
              typeof value === "number" ? formatPct(value) : "—",
              name === "inflation" ? "CPI inflation" : "Policy rate",
            ]}
          />
          <Legend
            wrapperStyle={{ fontSize: 12, color: "#1c1915" }}
            formatter={(value) => (value === "inflation" ? "CPI inflation (YoY %)" : "SARB policy rate (%)")}
          />
          <Line
            type="monotone"
            dataKey="inflation"
            name="inflation"
            stroke="#1e4f48"
            strokeWidth={2}
            dot={false}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="policyRate"
            name="policyRate"
            stroke="#c2410c"
            strokeWidth={2}
            dot={false}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
