"use client";

import { useSearchParams } from "next/navigation";
import ChatHistorySectionInner from "./ChatHistorySectionInner";

export default function ChatHistorySectionWithParams({
  isCollapsed,
  onNavigate,
}: {
  isCollapsed: boolean;
  onNavigate?: () => void;
}) {
  const searchParams = useSearchParams();
  const activeId = searchParams.get("id");
  return (
    <ChatHistorySectionInner
      isCollapsed={isCollapsed}
      onNavigate={onNavigate}
      activeId={activeId}
    />
  );
}
