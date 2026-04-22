"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { ChatHeader } from "./ChatHeader";
import { ChatMessages } from "./messages/ChatMessages";
import { ChatInput } from "./input/ChatInput";
import { TextAttachment } from "../types";
import { Preview } from "./attachment/Preview";
import { useAuth } from "@/lib/auth-context";
import { usePlugin } from "@/lib/plugins/context";
import { Alert } from "@/components/ui/Alert";
import { useConversation } from "../hooks/useConversation";
import { useCatalogDefaults } from "../hooks/useCatalogDefaults";
import { useChatStream } from "../hooks/useChatStream";

export default function ChatInterfaceInner({ conversationId }: { conversationId: string | null }) {
  const { token } = useAuth();
  const { config: chatConfig } = usePlugin("chat");
  const catalogDefaults = useCatalogDefaults(token);

  const provider = (chatConfig?.provider as string | undefined) ?? catalogDefaults?.provider;
  const model = (chatConfig?.model as string | undefined) ?? catalogDefaults?.model;
  const router = useRouter();
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewAttachment, setPreviewAttachment] = useState<TextAttachment | null>(null);

  const {
    loading: loadingHistory,
    messages,
    error,
    inputAttachment,
    setInputAttachment,
    setMessages,
    clearError,
    skipNextLoadRef,
  } = useConversation(conversationId, token);

  const onNewConversation = useCallback(
    (id: string) => {
      skipNextLoadRef.current = true;
      router.replace(`/dashboard/chat?id=${id}`);
    },
    [skipNextLoadRef, router],
  );

  const { handleSend, handleOptionClick } = useChatStream({
    token,
    provider,
    model,
    conversationId,
    setMessages,
    onNewConversation,
  });

  const handleSetAttachment = useCallback(
    (attachment: TextAttachment | null) => {
      setInputAttachment(attachment);
      if (attachment === null && conversationId && inputAttachment?.driveFileDbId) {
        fetch(`/api/v1/chat/conversations/${conversationId}/active-file`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        }).catch((err) => console.warn("Failed to clear active drive file on backend:", err));
      }
    },
    [setInputAttachment, conversationId, inputAttachment?.driveFileDbId, token],
  );

  return (
    <div className="flex flex-col h-full bg-background transition-colors">
      <ChatHeader />
      {error && (
        <div className="px-4 pt-4">
          <Alert severity="error" title="Something went wrong" onClose={clearError}>
            {error}
          </Alert>
        </div>
      )}

      {loadingHistory ? (
        <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
          Loading conversation…
        </div>
      ) : (
        <ChatMessages
          messages={messages}
          setPreviewOpen={setPreviewOpen}
          setPreviewAttachment={setPreviewAttachment}
          onSend={handleSend}
          onOptionClick={handleOptionClick}
        />
      )}

      <ChatInput
        attachment={inputAttachment}
        setAttachment={handleSetAttachment}
        setPreviewOpen={setPreviewOpen}
        setPreviewAttachment={setPreviewAttachment}
        onSend={handleSend}
      />

      {previewOpen && previewAttachment && (
        <Preview
          attachment={previewAttachment}
          onClose={() => {
            setPreviewOpen(false);
            setPreviewAttachment(null);
          }}
        />
      )}
    </div>
  );
}
