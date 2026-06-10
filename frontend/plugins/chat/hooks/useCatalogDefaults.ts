import { useCallback, useEffect, useState } from "react";
import { fetchProviderCatalog } from "@/lib/llm-api";

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
        const data = await fetchProviderCatalog(token, { signal });
        if (data.default_provider && data.default_model) {
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
