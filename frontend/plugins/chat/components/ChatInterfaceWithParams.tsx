"use client";

import HistoryColumn from "@/plugins/chat/components/history/HistoryColumn";
import { useActiveConversationId } from "@/plugins/chat/hooks/useActiveConversationId";
import ChatInterfaceInner from "./ChatInterfaceInner";

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
