import { Dispatch, SetStateAction, useCallback, useEffect, useRef, useState } from "react";
import { ChatMessage, TextAttachment } from "../types";
import {
  clearStreamProgress,
  getRestoredStreamData,
  RECOVERY_PLACEHOLDER_IDS,
} from "./useChatStream";

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
  setError: Dispatch<SetStateAction<string | null>>;
  inputAttachments: TextAttachment[];
  setInputAttachments: Dispatch<SetStateAction<TextAttachment[]>>;
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
        // Fetch messages and attachments in parallel — we need both before
        // picking the right placeholder text for a pending response.
        const [r, attachmentsRes] = await Promise.all([
          fetch(`/api/v1/chat/conversations/${conversationId}`, {
            headers: { Authorization: `Bearer ${token}` },
            signal,
          }),
          fetch(`/api/v1/chat/conversations/${conversationId}/attachments`, {
            headers: { Authorization: `Bearer ${token}` },
            signal,
          }),
        ]);
        if (!r.ok) throw new Error(`Load conversation failed with status ${r.status}`);
        const data: ApiConversation = await r.json();
        const persistedFiles: { id: number; name: string; size: number | null }[] =
          attachmentsRes.ok ? await attachmentsRes.json() : [];

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

        // If the last persisted message is from the user (no assistant response yet),
        // the previous stream was interrupted mid-flight. Restore whatever content
        // was buffered in sessionStorage so the partial response stays visible,
        // or show a context-aware placeholder while polling for the real message.
        const lastMsg = loaded[loaded.length - 1];
        if (conversationId && lastMsg?.role === "user") {
          const saved = getRestoredStreamData(conversationId);
          const hasAttachments = persistedFiles.length > 0;
          let placeholderContent: string;
          let placeholderId: string;

          if (saved?.content) {
            // Partial tokens arrived before the disconnect — show what we have.
            placeholderId = "restored-stream";
            placeholderContent = saved.content;
          } else if (
            hasAttachments ||
            saved?.phase === "scanning_attachments" ||
            saved?.phase === "searching_document"
          ) {
            // Attachments are present (RAG was likely running) or the phase was
            // explicitly saved — either way, scanning is the right framing.
            placeholderId = "pending-response";
            placeholderContent =
              "Still scanning your attached files — this may take a moment. The response will appear here automatically.";
          } else {
            placeholderId = "pending-response";
            placeholderContent =
              "Your response is still being generated. It will appear here automatically once ready.";
          }

          loaded.push({
            id: placeholderId,
            role: "assistant",
            content: placeholderContent,
            isTyping: false,
          });
        }

        setHistoryState({
          loading: false,
          messages: loaded.length ? loaded : [WELCOME_MESSAGE],
        });

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

  // Poll for the assistant response when we detected a pending response on load
  // (last DB message was user — backend was still generating when the page refreshed).
  // Replaces the recovery placeholder once the message is committed to DB.
  const hasPendingPlaceholder = historyState.messages.some((m) =>
    RECOVERY_PLACEHOLDER_IDS.has(m.id),
  );
  useEffect(() => {
    if (!hasPendingPlaceholder || !conversationId || !token) return;

    const POLL_INTERVAL_MS = 3_000;
    const POLL_TIMEOUT_MS = 5 * 60 * 1000; // stop after 5 min regardless
    const startedAt = Date.now();

    const intervalId = setInterval(async () => {
      if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
        clearInterval(intervalId);
        return;
      }
      try {
        const r = await fetch(`/api/v1/chat/conversations/${conversationId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!r.ok) return;
        const data: ApiConversation = await r.json();
        const lastApiMsg = data.messages[data.messages.length - 1];
        if (!lastApiMsg || lastApiMsg.role !== "assistant") return;

        // Response landed in DB — replace placeholder with the real message.
        clearStreamProgress(conversationId);
        setMessages((prev) => {
          const withoutPlaceholder = prev.filter((m) => !RECOVERY_PLACEHOLDER_IDS.has(m.id));
          return [
            ...withoutPlaceholder,
            {
              id: String(lastApiMsg.id),
              role: "assistant" as const,
              content: lastApiMsg.content,
              ragSections: lastApiMsg.rag_sections
                ? lastApiMsg.rag_sections.map((s) => ({ ...s, state: "confirmed" as const }))
                : undefined,
              isError: lastApiMsg.is_error ?? false,
            },
          ];
        });
        clearInterval(intervalId);
      } catch {
        // network error — will retry on next tick
      }
    }, POLL_INTERVAL_MS);

    return () => clearInterval(intervalId);
  }, [hasPendingPlaceholder, conversationId, token, setMessages]);

  return {
    loading: historyState.loading,
    messages: historyState.messages,
    error,
    setError,
    inputAttachments,
    setInputAttachments,
    setMessages,
    clearError: () => setError(null),
    skipNextLoadRef,
  };
}
