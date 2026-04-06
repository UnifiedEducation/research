"use client";

import {
  BarChart,
  Bar,
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
    items { rating }
  }
}`;

export default function RatingDistribution() {
  const { data, loading, error } = useGraphQL(QUERY);

  const chartData = (() => {
    if (!data) return [];
    const buckets: Record<string, number> = {};
    for (let i = 1; i <= 10; i++) {
      buckets[`${i}`] = 0;
    }
    for (const f of data.films.items) {
      const bucket = `${Math.ceil(f.rating)}`;
      if (buckets[bucket] !== undefined) buckets[bucket]++;
    }
    return Object.entries(buckets).map(([rating, count]) => ({
      rating,
      count,
    }));
  })();

  return (
    <ChartCard title="Rating Distribution" loading={loading} error={error}>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="rating" label={{ value: "Rating", position: "insideBottom", offset: -5 }} />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
