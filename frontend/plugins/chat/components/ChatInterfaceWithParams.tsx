"use client";

import { useActiveConversationId } from "@/plugins/chat/hooks/useActiveConversationId";
import ChatInterfaceInner from "./ChatInterfaceInner";

export default function ChatInterfaceWithParams() {
  const conversationId = useActiveConversationId();
  return <ChatInterfaceInner conversationId={conversationId} />;
}
