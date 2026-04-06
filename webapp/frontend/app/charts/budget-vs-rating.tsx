"use client";

import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useGraphQL } from "../use-graphql";
import ChartCard from "./chart-card";

const QUERY = `{
  films {
    items { title budget rating }
  }
}`;

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-white border border-gray-200 rounded px-3 py-2 text-sm shadow">
      <p className="font-semibold">{d.title}</p>
      <p>Budget: ${(d.budget / 1_000_000).toFixed(0)}M</p>
      <p>Rating: {d.rating}</p>
    </div>
  );
}

export default function BudgetVsRating() {
  const { data, loading, error } = useGraphQL(QUERY);

  const chartData = data
    ? data.films.items
        .filter((f: any) => f.budget && f.rating)
        .map((f: any) => ({
          title: f.title,
          budget: f.budget,
          rating: f.rating,
        }))
    : [];

  return (
    <ChartCard title="Budget vs Rating" loading={loading} error={error}>
      <ResponsiveContainer width="100%" height={300}>
        <ScatterChart margin={{ bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="budget"
            type="number"
            tickFormatter={(v) => `$${(v / 1_000_000).toFixed(0)}M`}
            label={{ value: "Budget", position: "insideBottom", offset: -5 }}
          />
          <YAxis dataKey="rating" type="number" domain={[0, 10]} label={{ value: "Rating", angle: -90, position: "insideLeft" }} />
          <Tooltip content={<CustomTooltip />} />
          <Scatter data={chartData} fill="#10b981" />
        </ScatterChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
