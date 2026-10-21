"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { PERIOD_KEYS, parsePeriod, periodQuery, toIsoDate, type Period } from "@/lib/analytics";

export function usePeriod() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const today = toIsoDate(new Date());
  const query = params.toString();
  const { period, error } = useMemo(
    () => parsePeriod(new URLSearchParams(query), today),
    [query, today],
  );
  // The last query written but not yet in the URL: router.replace lands after a commit, so a
  // second change made before then must build on the first, not on the rendered period.
  const pending = useRef<string | null>(null);
  useEffect(() => {
    pending.current = null;
  }, [query]);
  const setPeriod = useCallback(
    (update: (current: Period) => Period) => {
      const params = new URLSearchParams(pending.current ?? query);
      const current = parsePeriod(params, today).period;
      // A view's own settings (Explore's) stay after the period.
      const rest = new URLSearchParams([...params].filter(([k]) => !PERIOD_KEYS.includes(k)));
      const next = [periodQuery(update(current)), rest.toString()].filter(Boolean).join("&");
      pending.current = next;
      router.replace(`${pathname}?${next}`);
    },
    [router, pathname, query, today],
  );
  return { period, error, setPeriod };
}
