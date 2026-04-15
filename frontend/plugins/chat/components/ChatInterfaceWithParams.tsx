"use client";

import { useSearchParams } from "next/navigation";
import ChatInterfaceInner from "./ChatInterfaceInner";

export default function ChatInterfaceWithParams() {
  const searchParams = useSearchParams();
  const conversationId = searchParams.get("id");
  return <ChatInterfaceInner conversationId={conversationId} />;
}
