"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export default function AnalyticsIndex() {
  const router = useRouter();
  const query = useSearchParams().toString();
  useEffect(() => {
    router.replace(`/dashboard/analytics/logins${query ? `?${query}` : ""}`);
  }, [router, query]);
  return null;
}
