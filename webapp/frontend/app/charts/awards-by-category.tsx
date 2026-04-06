"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useGraphQL } from "../use-graphql";
import ChartCard from "./chart-card";

const QUERY = `{
  awards {
    items { category }
  }
}`;

const COLORS = [
  "#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444",
  "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#6366f1",
];

export default function AwardsByCategory() {
  const { data, loading, error } = useGraphQL(QUERY);

  const chartData = (() => {
    if (!data) return [];
    const counts: Record<string, number> = {};
    for (const a of data.awards.items) {
      const cat = a.category || "Unknown";
      counts[cat] = (counts[cat] || 0) + 1;
    }
    return Object.entries(counts)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value);
  })();

  return (
    <ChartCard title="Awards by Category" loading={loading} error={error}>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={chartData}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            outerRadius={100}
            label={(props: any) =>
              `${props.name} (${((props.percent || 0) * 100).toFixed(0)}%)`
            }
            labelLine={true}
            fontSize={11}
          >
            {chartData.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
