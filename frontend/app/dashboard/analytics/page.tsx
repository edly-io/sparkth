"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// No Overview yet (#758): the analytics root forwards to the first view. Client-side because
// the production build is a static export with no server to redirect.
export default function AnalyticsIndex() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/dashboard/analytics/logins");
  }, [router]);
  return null;
}
