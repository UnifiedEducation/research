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
  genres {
    items {
      name
      film { items { FilmID } }
    }
  }
}`;

export default function FilmsByGenre() {
  const { data, loading, error } = useGraphQL(QUERY);

  const chartData = data
    ? data.genres.items
        .map((g: any) => ({
          genre: g.name,
          count: g.film?.items?.length || 0,
        }))
        .sort((a: any, b: any) => b.count - a.count)
    : [];

  return (
    <ChartCard title="Films by Genre" loading={loading} error={error}>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData} layout="vertical" margin={{ left: 80 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" allowDecimals={false} />
          <YAxis type="category" dataKey="genre" width={75} fontSize={12} />
          <Tooltip />
          <Bar dataKey="count" fill="#3b82f6" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
