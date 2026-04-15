"use client";

import { Suspense } from "react";
import ChatHistorySectionInner from "./ChatHistorySectionInner";

interface ChatHistorySectionProps {
  isCollapsed: boolean;
  onNavigate?: () => void;
}

export function ChatHistorySection(props: ChatHistorySectionProps) {
  return (
    <Suspense fallback={null}>
      <ChatHistorySectionInner {...props} />
    </Suspense>
  );
}
