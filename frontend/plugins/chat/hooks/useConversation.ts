import { useCallback, useEffect, useRef, useState } from "react";
import { ChatMessage, TextAttachment } from "../types";

function mergeConsecutiveAttachmentMessages(messages: ChatMessage[]): ChatMessage[] {
  const result: ChatMessage[] = [];
  let i = 0;
  while (i < messages.length) {
    const msg = messages[i];
    if (msg.role === "user" && msg.attachments && msg.attachments.length > 0) {
      const attachments: TextAttachment[] = [...msg.attachments];
      let content = msg.content;
      let lastId = msg.id;
      while (
        i + 1 < messages.length &&
        messages[i + 1].role === "user" &&
        messages[i + 1].attachments &&
        messages[i + 1].attachments!.length > 0
      ) {
        i++;
        const next = messages[i];
        attachments.push(...next.attachments!);
        if (next.content) content = next.content;
        lastId = next.id;
      }
      result.push({ ...msg, id: lastId, attachments, content });
    } else {
      result.push(msg);
    }
    i++;
  }
  return result;
}

const WELCOME_MESSAGE: ChatMessage = {
  id: "welcome",
  role: "assistant",
  content: "Hi! Upload a document or tell me what you'd like to create.",
};

interface ApiMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  message_type: "text" | "attachment";
  attachment_name: string | null;
  attachment_size: number | null;
  created_at: string;
  rag_sections: { type: string; name: string; source?: string }[] | null;
  is_error: boolean;
}

interface ApiConversation {
  id: string;
  messages: ApiMessage[];
}

interface UseConversationResult {
  loading: boolean;
  messages: ChatMessage[];
  error: string | null;
  inputAttachments: TextAttachment[];
  setInputAttachments: (attachments: TextAttachment[]) => void;
  setMessages: (updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => void;
  clearError: () => void;
  skipNextLoadRef: React.RefObject<boolean>;
}

export function useConversation(
  conversationId: string | null,
  token: string | null,
): UseConversationResult {
  const [error, setError] = useState<string | null>(null);
  const [inputAttachments, setInputAttachments] = useState<TextAttachment[]>([]);
  // Prevents loadConversation from overwriting messages when we navigated there ourselves
  const skipNextLoadRef = useRef(false);
  const [historyState, setHistoryState] = useState<{
    loading: boolean;
    messages: ChatMessage[];
  }>({
    loading: !!conversationId,
    messages: conversationId ? [] : [WELCOME_MESSAGE],
  });

  const setMessages = useCallback(
    (updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) =>
      setHistoryState((prev) => ({
        ...prev,
        messages: typeof updater === "function" ? updater(prev.messages) : updater,
      })),
    [],
  );

  const loadConversation = useCallback(
    async (signal: AbortSignal) => {
      if (!conversationId) {
        setHistoryState({
          loading: false,
          messages: [WELCOME_MESSAGE],
        });
        setInputAttachments([]);
        return;
      }

      // We just navigated here ourselves after a send — keep current messages state
      if (skipNextLoadRef.current) {
        skipNextLoadRef.current = false;
        return;
      }

      setHistoryState({ loading: true, messages: [] });
      try {
        const r = await fetch(`/api/v1/chat/conversations/${conversationId}`, {
          headers: { Authorization: `Bearer ${token}` },
          signal,
        });
        if (!r.ok) throw new Error(`Load conversation failed with status ${r.status}`);
        const data: ApiConversation = await r.json();
        const loaded: ChatMessage[] = mergeConsecutiveAttachmentMessages(
          data.messages.map((m) => ({
            id: String(m.id),
            role: m.role,
            content:
              m.message_type === "attachment"
                ? m.content !== "[File attachment]"
                  ? m.content
                  : ""
                : m.content,
            attachments:
              m.message_type === "attachment" && m.attachment_name
                ? [{ name: m.attachment_name, size: m.attachment_size ?? 0, text: m.content }]
                : undefined,
            ragSections: m.rag_sections
              ? m.rag_sections.map((s) => ({ ...s, state: "confirmed" as const }))
              : undefined,
            isError: m.is_error ?? false,
          })),
        );
        setHistoryState({
          loading: false,
          messages: loaded.length ? loaded : [WELCOME_MESSAGE],
        });

        // Load persisted drive file attachments from the join table.
        const attachmentsRes = await fetch(
          `/api/v1/chat/conversations/${conversationId}/attachments`,
          {
            headers: { Authorization: `Bearer ${token}` },
            signal,
          },
        );
        const persistedFiles: { id: number; name: string; size: number | null }[] =
          attachmentsRes.ok ? await attachmentsRes.json() : [];

        setInputAttachments(
          persistedFiles.map((f) => ({
            name: f.name,
            size: f.size ?? 0,
            text: `[File: ${f.name}]`,
            driveFileDbId: f.id,
          })),
        );
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        console.error(err);
        setError("Failed to load conversation. Please try again.");
        setHistoryState({ loading: false, messages: [WELCOME_MESSAGE] });
      }
    },
    [conversationId, token],
  );

  useEffect(() => {
    const controller = new AbortController();
    loadConversation(controller.signal);
    return () => controller.abort();
  }, [loadConversation]);

  return {
    loading: historyState.loading,
    messages: historyState.messages,
    error,
    inputAttachments,
    setInputAttachments,
    setMessages,
    clearError: () => setError(null),
    skipNextLoadRef,
  };
}
