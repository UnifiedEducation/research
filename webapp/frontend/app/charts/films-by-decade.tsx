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
    items { releaseYear }
  }
}`;

export default function FilmsByDecade() {
  const { data, loading, error } = useGraphQL(QUERY);

  const chartData = (() => {
    if (!data) return [];
    const decades: Record<string, number> = {};
    for (const f of data.films.items) {
      if (!f.releaseYear) continue;
      const decade = `${Math.floor(f.releaseYear / 10) * 10}s`;
      decades[decade] = (decades[decade] || 0) + 1;
    }
    return Object.entries(decades)
      .map(([decade, count]) => ({ decade, count }))
      .sort((a, b) => a.decade.localeCompare(b.decade));
  })();

  return (
    <ChartCard title="Films by Decade" loading={loading} error={error}>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="decade" />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Bar dataKey="count" fill="#06b6d4" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
