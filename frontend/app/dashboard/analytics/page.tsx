"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

// No Overview view yet: the analytics root forwards to the first view, keeping any period in
// the query. Client-side because the production build is a static export with no server to
// redirect; useSearchParams is covered by the layout's Suspense boundary.
export default function AnalyticsIndex() {
  const router = useRouter();
  const query = useSearchParams().toString();
  useEffect(() => {
    router.replace(`/dashboard/analytics/logins${query ? `?${query}` : ""}`);
  }, [router, query]);
  return null;
}
