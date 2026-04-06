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
  directors {
    items {
      name
      directs { items { title rating } }
    }
  }
}`;

export default function TopDirectors() {
  const { data, loading, error } = useGraphQL(QUERY);

  const chartData = data
    ? data.directors.items
        .map((d: any) => {
          const films = d.directs?.items || [];
          const avgRating =
            films.length > 0
              ? films.reduce((sum: number, f: any) => sum + (f.rating || 0), 0) /
                films.length
              : 0;
          return {
            name: d.name,
            films: films.length,
            avgRating: Math.round(avgRating * 10) / 10,
          };
        })
        .filter((d: any) => d.films > 0)
        .sort((a: any, b: any) => b.avgRating - a.avgRating)
        .slice(0, 10)
    : [];

  return (
    <ChartCard title="Top 10 Directors (Avg Rating)" loading={loading} error={error}>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData} layout="vertical" margin={{ left: 100 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" domain={[0, 10]} />
          <YAxis type="category" dataKey="name" width={95} fontSize={12} />
          <Tooltip
            formatter={(value: any, name: any) =>
              name === "avgRating" ? [value, "Avg Rating"] : [value, name]
            }
          />
          <Bar dataKey="avgRating" fill="#f59e0b" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
