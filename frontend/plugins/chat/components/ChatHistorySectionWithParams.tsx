"use client";

import { useActiveConversationId } from "@/plugins/chat/hooks/useActiveConversationId";
import ChatHistorySectionInner from "./ChatHistorySectionInner";

export default function ChatHistorySectionWithParams({
  isCollapsed,
  onNavigate,
}: {
  isCollapsed: boolean;
  onNavigate?: () => void;
}) {
  const activeId = useActiveConversationId();
  return (
    <ChatHistorySectionInner
      isCollapsed={isCollapsed}
      onNavigate={onNavigate}
      activeId={activeId}
    />
  );
}
