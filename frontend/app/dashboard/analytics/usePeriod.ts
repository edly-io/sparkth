"use client";

import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { parsePeriod, periodQuery, toIsoDate, type Period } from "@/lib/analytics";

// The analytics period lives only in the URL, so it survives reloads, view switches and
// shared links. `replace`, not `push`: tweaking the period shouldn't flood Back.
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
  const setPeriod = useCallback(
    (next: Period) => router.replace(`${pathname}?${periodQuery(next)}`),
    [router, pathname],
  );
  return { period, error, setPeriod };
}
