"use client";

import { ReactNode } from "react";

export default function ChartCard({
  title,
  loading,
  error,
  children,
}: {
  title: string;
  loading: boolean;
  error: string | null;
  children: ReactNode;
}) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
      <h2 className="text-lg font-semibold text-gray-800 mb-4">{title}</h2>
      {loading && (
        <div className="flex items-center justify-center h-64 text-gray-400">
          Loading...
        </div>
      )}
      {error && (
        <div className="flex items-center justify-center h-64 text-red-500 text-sm">
          {error}
        </div>
      )}
      {!loading && !error && children}
    </div>
  );
}
