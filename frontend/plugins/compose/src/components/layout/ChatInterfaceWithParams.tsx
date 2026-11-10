"use client";

import HistoryColumn from "@/plugins/compose/src/components/ui/history/HistoryColumn";
import { useActiveConversationId } from "@/plugins/compose/src/hooks/useActiveConversationId";
import ChatInterfaceInner from "@/plugins/compose/src/components/layout/ChatInterfaceInner";

export default function ChatInterfaceWithParams() {
  const conversationId = useActiveConversationId();
  return (
    <div className="flex h-full">
      <HistoryColumn />
      <div className="flex-1 min-w-0 h-full">
        <ChatInterfaceInner conversationId={conversationId} />
      </div>
    </div>
  );
}
