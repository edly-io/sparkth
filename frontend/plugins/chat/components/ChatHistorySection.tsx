"use client";

import { Suspense } from "react";
import ChatHistorySectionWithParams from "./ChatHistorySectionWithParams";

interface ChatHistorySectionProps {
  isCollapsed: boolean;
  onNavigate?: () => void;
}

export function ChatHistorySection(props: ChatHistorySectionProps) {
  return (
    <Suspense fallback={null}>
      <ChatHistorySectionWithParams {...props} />
    </Suspense>
  );
}
