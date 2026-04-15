import { useCallback, useEffect, useRef, useState } from "react";
import { ChatMessage, TextAttachment } from "../types";

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
}

interface ApiConversation {
  id: string;
  messages: ApiMessage[];
  active_drive_file_id: number | null;
  active_drive_file_name: string | null;
}

interface UseConversationResult {
  loading: boolean;
  messages: ChatMessage[];
  error: string | null;
  inputAttachment: TextAttachment | null;
  setInputAttachment: (attachment: TextAttachment | null) => void;
  setMessages: (
    updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[]),
  ) => void;
  clearError: () => void;
  skipNextLoadRef: React.RefObject<boolean>;
}

export function useConversation(
  conversationId: string | null,
  token: string | null,
): UseConversationResult {
  const [error, setError] = useState<string | null>(null);
  const [inputAttachment, setInputAttachment] = useState<TextAttachment | null>(null);
  // Prevents loadConversation from overwriting messages when we navigated there ourselves
  const skipNextLoadRef = useRef(false);
  const [historyState, setHistoryState] = useState<{
    loading: boolean;
    messages: ChatMessage[];
  }>({
    loading: !!conversationId,
    messages: conversationId ? [] : [WELCOME_MESSAGE],
  });

  const setMessages = (
    updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[]),
  ) =>
    setHistoryState((prev) => ({
      ...prev,
      messages:
        typeof updater === "function" ? updater(prev.messages) : updater,
    }));

  const loadConversation = useCallback(
    async (signal: AbortSignal) => {
      if (!conversationId) {
        setHistoryState({
          loading: false,
          messages: [WELCOME_MESSAGE],
        });
        setInputAttachment(null);
        return;
      }

      // We just navigated here ourselves after a send — keep current messages state
      if (skipNextLoadRef.current) {
        skipNextLoadRef.current = false;
        return;
      }

      setHistoryState({ loading: true, messages: [] });
      try {
        const r = await fetch(
          `/api/v1/chat/conversations/${conversationId}`,
          {
            headers: { Authorization: `Bearer ${token}` },
            signal,
          },
        );
        if (!r.ok)
          throw new Error(`Load conversation failed with status ${r.status}`);
        const data: ApiConversation = await r.json();
        const loaded: ChatMessage[] = data.messages.map((m) => ({
          id: String(m.id),
          role: m.role,
          content:
            m.message_type === "attachment"
              ? m.content !== "[File attachment]"
                ? m.content
                : ""
              : m.content,
          attachment:
            m.message_type === "attachment" && m.attachment_name
              ? {
                  name: m.attachment_name,
                  size: m.attachment_size ?? 0,
                  text: m.content,
                }
              : undefined,
        }));
        setHistoryState({
          loading: false,
          messages: loaded.length ? loaded : [WELCOME_MESSAGE],
        });

        // Restore persistent drive file attachment (or clear if this conversation has none)
        if (data.active_drive_file_id && data.active_drive_file_name) {
          setInputAttachment({
            name: data.active_drive_file_name,
            size: 0,
            text: `[File: ${data.active_drive_file_name}]`,
            driveFileDbId: data.active_drive_file_id,
          });
        } else {
          setInputAttachment(null);
        }
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
    inputAttachment,
    setInputAttachment,
    setMessages,
    clearError: () => setError(null),
    skipNextLoadRef,
  };
}
