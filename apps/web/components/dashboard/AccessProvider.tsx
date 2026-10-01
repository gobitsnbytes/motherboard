"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { type EffectiveAccess } from "../../lib/access";

const AccessContext = createContext<{
  access: EffectiveAccess | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}>({ access: null, loading: true, error: null, refresh: async () => {} });

export function AccessProvider({ children }: { children: React.ReactNode }) {
  const [access, setAccess] = useState<EffectiveAccess | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const activeRequest = useRef<AbortController | null>(null);
  const refresh = useCallback(async () => {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setLoading(true);
    try {
      const response = await fetch("/api/iam/me", { cache: "no-store", signal: controller.signal });
      if (!response.ok) throw new Error("Your access could not be loaded. Retry to refresh it.");
      const result = await response.json();
      if (controller.signal.aborted) return;
      setAccess(result);
      setError(null);
    } catch (err) {
      if (controller.signal.aborted) return;
      setAccess(null);
      setError(err instanceof Error ? err.message : "Access is unavailable.");
    } finally { if (!controller.signal.aborted) setLoading(false); }
  }, []);
  useEffect(() => { void refresh(); return () => activeRequest.current?.abort(); }, [refresh]);
  return <AccessContext.Provider value={{ access, loading, error, refresh }}>{children}</AccessContext.Provider>;
}

export function useAccess() { return useContext(AccessContext); }
