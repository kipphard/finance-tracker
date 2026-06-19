import { useCallback, useEffect, useState } from "react";
import { apiGet } from "../api/client";

export interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

// Fetch a GET endpoint with loading/error state and a manual reload trigger.
export function useApi<T>(path: string): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const reload = useCallback(() => setTick((t) => t + 1), []);

  // Refetch whenever any mutation happens anywhere in the app.
  useEffect(() => {
    const onChange = () => setTick((t) => t + 1);
    window.addEventListener("ft-data-changed", onChange);
    return () => window.removeEventListener("ft-data-changed", onChange);
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    apiGet<T>(path)
      .then((d) => {
        if (active) {
          setData(d);
          setError(null);
        }
      })
      .catch((e: unknown) => {
        if (active) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [path, tick]);

  return { data, loading, error, reload };
}
