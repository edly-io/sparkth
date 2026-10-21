"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { PERIOD_KEYS, parsePeriod, periodQuery, toIsoDate, type Period } from "@/lib/analytics";

// The last query written but not yet in the URL, shared by every writer on the page:
// router.replace lands after a commit, so a second change made before then, by the same control
// or another, must build on the first, not on the rendered URL.
let pending: string | null = null;

/**
 * Replaces the URL's query with `build(latest)`, where `latest` includes any write still in
 * flight. Does nothing when the query would not change. The returned function is stable, so an
 * async callback can call it after later renders.
 */
export function useReplaceQuery() {
  const router = useRouter();
  const pathname = usePathname();
  const query = useSearchParams().toString();
  const rendered = useRef(query);
  useEffect(() => {
    rendered.current = query;
    pending = null;
  }, [query]);
  return useCallback(
    (build: (latest: URLSearchParams) => string) => {
      const latest = pending ?? rendered.current;
      const next = build(new URLSearchParams(latest));
      if (next === latest) return;
      pending = next;
      router.replace(next ? `${pathname}?${next}` : pathname);
    },
    [router, pathname],
  );
}

export function usePeriod() {
  const query = useSearchParams().toString();
  const today = toIsoDate(new Date());
  const { period, error } = useMemo(
    () => parsePeriod(new URLSearchParams(query), today),
    [query, today],
  );
  const replaceQuery = useReplaceQuery();
  const setPeriod = useCallback(
    (update: (current: Period) => Period) =>
      replaceQuery((latest) => {
        const current = parsePeriod(latest, today).period;
        // A view's own settings (Explore's) stay after the period.
        const rest = new URLSearchParams([...latest].filter(([k]) => !PERIOD_KEYS.includes(k)));
        return [periodQuery(update(current)), rest.toString()].filter(Boolean).join("&");
      }),
    [replaceQuery, today],
  );
  return { period, error, setPeriod };
}
