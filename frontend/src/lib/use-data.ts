"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
export function useData<T>(endpoint: string | null) {
  const [state, setState] = useState<{
    endpoint: string | null;
    revision: number;
    data: T | null;
    error: string | null;
  }>({ endpoint: null, revision: -1, data: null, error: null });
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    if (!endpoint) return;
    const controller = new AbortController();
    api<T>(endpoint, { signal: controller.signal })
      .then((data) => setState({ endpoint, revision, data, error: null }))
      .catch((error) => {
        if (error.name === "AbortError") return;
        setState({
          endpoint,
          revision,
          data: null,
          error: error.message || "خطا در دریافت اطلاعات",
        });
      });
    return () => controller.abort();
  }, [endpoint, revision]);
  const current = state.endpoint === endpoint;
  return {
    data: current ? state.data : null,
    error: current ? state.error : null,
    loading: !current || revision !== state.revision,
    refresh,
  };
}
