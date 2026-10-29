"use client";

import { useSearchParams } from "next/navigation";

export function useActiveConversationId() {
  const searchParams = useSearchParams();
  return searchParams.get("id");
}
