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
import { useChatStream } from "../hooks/useChatStream";

export default function ChatInterfaceInner({ conversationId }: { conversationId: string | null }) {
  const { token } = useAuth();
  const { config: chatConfig } = usePlugin("chat");

  const rawId = chatConfig?.llm_config_id;
  const llmConfigId = rawId != null ? Number(rawId) : undefined;
  const modelOverride = (chatConfig?.llm_model_override as string | null | undefined) ?? undefined;
  const router = useRouter();
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewAttachment, setPreviewAttachment] = useState<TextAttachment | null>(null);

  const {
    loading: loadingHistory,
    messages,
    error,
    setError,
    inputAttachments,
    setInputAttachments,
    setMessages,
    clearError,
    skipNextLoadRef,
  } = useConversation(conversationId, token);

  const onNewConversation = useCallback(
    (id: string) => {
      skipNextLoadRef.current = true;
      router.replace(`/dashboard/chat?id=${id}`);
      // Sync any drive files that were selected before the conversation existed
      for (const att of inputAttachments) {
        if (att.driveFileDbId !== undefined) {
          fetch(`/api/v1/chat/conversations/${id}/attachments`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
            body: JSON.stringify({ drive_file_id: att.driveFileDbId }),
          })
            .then((res) => {
              if (!res.ok) throw new Error(`HTTP ${res.status}`);
            })
            .catch((err) => {
              console.warn("Failed to persist drive file attachment on new conversation:", err);
              setError(
                `Failed to attach "${att.name}". It may not be available for this conversation.`,
              );
            });
        }
      }
    },
    [skipNextLoadRef, router, inputAttachments, token, setError],
  );

  const { handleSend, handleOptionClick } = useChatStream({
    token,
    llmConfigId,
    modelOverride,
    conversationId,
    setMessages,
    onNewConversation,
  });

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
        attachments={inputAttachments}
        setAttachments={setInputAttachments}
        onSend={handleSend}
        conversationId={conversationId}
      />

      {previewOpen && previewAttachment && (
        <Preview attachment={previewAttachment} onClose={() => setPreviewOpen(false)} />
      )}
    </div>
  );
}
