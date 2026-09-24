"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { ChatHeader } from "./ChatHeader";
import { ChatMessages } from "./messages/ChatMessages";
import { ChatInput } from "./input/ChatInput";
import { AiKeyProblem, TextAttachment } from "../types";
import { Preview } from "./attachment/Preview";
import { useAuth } from "@/lib/auth-context";
import { attachDocument } from "@/lib/chat";
import { fetchLLMConfigs } from "@/lib/llm/client";
import { usePlugin } from "@/lib/plugins/context";
import { Alert } from "@/components/ui/Alert";
import { useConversation } from "../hooks/useConversation";
import { useChatStream } from "../hooks/useChatStream";

// Only reached when no key is selected, so a correctly configured author never pays for it.
async function readAiKeyProblem(token: string): Promise<AiKeyProblem> {
  try {
    const { total } = await fetchLLMConfigs(token);
    return total > 0 ? "not-selected" : "no-key";
  } catch (err) {
    // An unknown account is not an empty one; the gentler message is the honest one.
    console.error("Failed to read the AI keys on this account:", err);
    return "not-selected";
  }
}

export default function ChatInterfaceInner({ conversationId }: { conversationId: string | null }) {
  const { token } = useAuth();
  const { config: chatConfig } = usePlugin("chat");
  const t = useTranslations("chat");

  const rawId = chatConfig?.llm_config_id;
  const llmConfigId = rawId != null ? Number(rawId) : undefined;
  const modelOverride = (chatConfig?.llm_model_override as string | null | undefined) ?? undefined;
  const router = useRouter();
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewAttachment, setPreviewAttachment] = useState<TextAttachment | null>(null);
  const [aiKeyProblem, setAiKeyProblem] = useState<AiKeyProblem | null>(null);
  const inFlightCheckRef = useRef<Promise<AiKeyProblem | null> | null>(null);

  // A concurrent second send shares this in-flight check instead of starting its own —
  // otherwise both could observe "ready" from a config that just landed and both dispatch.
  const checkAiKeyReady = useCallback((): Promise<AiKeyProblem | null> => {
    if (llmConfigId != null || !token) {
      setAiKeyProblem(null);
      return Promise.resolve(null);
    }
    if (inFlightCheckRef.current) return inFlightCheckRef.current;
    const pending = readAiKeyProblem(token).finally(() => {
      inFlightCheckRef.current = null;
    });
    inFlightCheckRef.current = pending;
    return pending;
  }, [llmConfigId, token]);

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
        if (att.documentId !== undefined) {
          attachDocument(token, id, att.documentId).catch((err) => {
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

  const { handleSend, handleOptionClick, stopGeneration, isStopping } = useChatStream({
    token,
    llmConfigId,
    modelOverride,
    conversationId,
    setMessages,
    onNewConversation,
  });

  // Every send path runs through this, and it resolves false when it refuses the send.
  const sendIfAiKeyReady = useCallback(
    async (dispatch: () => void): Promise<boolean> => {
      const problem = await checkAiKeyReady();
      if (problem) {
        setAiKeyProblem(problem);
        return false;
      }
      dispatch();
      return true;
    },
    [checkAiKeyReady],
  );

  const handleGuardedSend = useCallback(
    (payload: { message: string; attachments: TextAttachment[]; documentIds?: number[] }) =>
      sendIfAiKeyReady(() => handleSend(payload)),
    [sendIfAiKeyReady, handleSend],
  );

  const handleGuardedOptionClick = useCallback(
    (text: string) => sendIfAiKeyReady(() => handleOptionClick(text)),
    [sendIfAiKeyReady, handleOptionClick],
  );

  const isStreaming = messages.some((m) => m.isTyping === true);

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

      {aiKeyProblem && (
        <div className="px-4 pt-4">
          <Alert severity="warning" onClose={() => setAiKeyProblem(null)}>
            {aiKeyProblem === "no-key" ? t("aiKeyMissing") : t("aiKeyNotSelected")}{" "}
            <Link
              href={aiKeyProblem === "no-key" ? "/dashboard/llm/configure" : "/dashboard/settings"}
              className="underline"
            >
              {aiKeyProblem === "no-key" ? t("aiKeyMissingAction") : t("aiKeyNotSelectedAction")}
            </Link>
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
          onSend={handleGuardedSend}
          onOptionClick={handleGuardedOptionClick}
        />
      )}

      <ChatInput
        attachments={inputAttachments}
        setAttachments={setInputAttachments}
        onSend={handleGuardedSend}
        conversationId={conversationId}
        isStreaming={isStreaming}
        isStopping={isStopping}
        onStop={stopGeneration}
      />

      {previewOpen && previewAttachment && (
        <Preview attachment={previewAttachment} onClose={() => setPreviewOpen(false)} />
      )}
    </div>
  );
}
