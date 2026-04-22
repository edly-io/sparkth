import { useCallback, useEffect, useState } from "react";

interface CatalogDefaults {
  provider: string;
  model: string;
}

export function useCatalogDefaults(token: string | null): CatalogDefaults | null {
  const [defaults, setDefaults] = useState<CatalogDefaults | null>(null);

  const fetchDefaults = useCallback(
    async (signal: AbortSignal) => {
      if (!token) return;
      try {
        const r = await fetch("/api/v1/chat/providers", {
          headers: { Authorization: `Bearer ${token}` },
          signal,
        });
        if (!r.ok) return;
        const data = await r.json();
        if (data?.default_provider && data?.default_model) {
          setDefaults({ provider: data.default_provider, model: data.default_model });
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        console.warn("Failed to fetch chat provider defaults:", err);
      }
    },
    [token],
  );

  useEffect(() => {
    const controller = new AbortController();
    fetchDefaults(controller.signal);
    return () => controller.abort();
  }, [fetchDefaults]);

  return defaults;
}
