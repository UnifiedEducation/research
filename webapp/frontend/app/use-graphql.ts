"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "./msal-provider";

// In production (static export served by FastAPI), BACKEND_URL is empty (same origin).
// In local dev, set NEXT_PUBLIC_BACKEND_URL=http://localhost:8000 in .env.local.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "";

interface UseGraphQLResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useGraphQL<T = any>(query: string): UseGraphQLResult<T> {
  const { isAuthenticated, getToken } = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) {
        setError("Failed to acquire token");
        return;
      }
      const res = await fetch(`${BACKEND_URL}/api/graphql`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query }),
      });
      const json = await res.json();
      if (json.errors) {
        setError(json.errors[0]?.message || "GraphQL error");
      } else {
        setData(json.data);
      }
    } catch (err) {
      setError(`${err}`);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated, getToken, query]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}
