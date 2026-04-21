"use client";

import { useSearchParams } from "next/navigation";

export function useCallbackParams() {
  const searchParams = useSearchParams();
  return {
    token: searchParams.get("token"),
    expiresAt: searchParams.get("expires_at"),
    errorParam: searchParams.get("error"),
  };
}
