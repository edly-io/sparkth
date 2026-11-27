import { Dispatch, SetStateAction, useCallback, useEffect, useRef, useState } from "react";
import { ApiRequestError, isNotFoundError } from "@/lib/api/errors";
import {
  getConversation,
  getConversationAttachments,
  getConversationUploadedFiles,
  getLastMessage,
} from "@/plugins/compose/src/client";
import {
  type ApiMessage,
  ChatMessage,
  ChatRole,
  type ConversationLoadError,
  TextAttachment,
} from "@/plugins/compose/src/types";
import {
  clearStreamProgress,
  getRestoredStreamData,
  RECOVERY_PLACEHOLDER_IDS,
} from "@/plugins/compose/src/hooks/useChatStream";

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

// Compose refuses someone else's chat with a 403: to the author, that chat does not exist either.
function getLoadError(error: unknown): ConversationLoadError {
  const refused = error instanceof ApiRequestError && error.status === 403;
  return isNotFoundError(error) || refused ? "notFound" : "failed";
}

interface UseConversationResult {
  loading: boolean;
  messages: ChatMessage[];
  loadError: ConversationLoadError | null;
  error: string | null;
  setError: Dispatch<SetStateAction<string | null>>;
  inputMessage: string;
  setInputMessage: Dispatch<SetStateAction<string>>;
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
  const [loadError, setLoadError] = useState<ConversationLoadError | null>(null);
  const [inputMessage, setInputMessage] = useState("");
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
      // We just navigated here ourselves after a send — keep current messages state
      if (conversationId && skipNextLoadRef.current) {
        skipNextLoadRef.current = false;
        return;
      }

      // A different chat starts with an empty box and without the last chat's errors.
      setError(null);
      setLoadError(null);
      setInputMessage("");

      if (!conversationId) {
        setHistoryState({
          loading: false,
          messages: [WELCOME_MESSAGE],
        });
        setInputAttachments([]);
        return;
      }

      setHistoryState({ loading: true, messages: [] });
      try {
        // Fetch messages and attachments in parallel; we need both before
        // picking the right placeholder text for a pending response.
        const [data, persistedFiles, uploadedFiles] = await Promise.all([
          getConversation(token, conversationId, signal),
          getConversationAttachments(token, conversationId, signal),
          getConversationUploadedFiles(token, conversationId, signal),
        ]);

        const transcript = data.messages.filter(
          (m): m is ApiMessage & { role: ChatRole } => m.role === "user" || m.role === "assistant",
        );
        const loaded: ChatMessage[] = mergeConsecutiveAttachmentMessages(
          transcript.map((m) => ({
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
                ? [
                    {
                      name: m.attachment_name,
                      size: m.attachment_size ?? 0,
                      text: m.content,
                    },
                  ]
                : undefined,
            ragSections: m.rag_sections
              ? m.rag_sections.map((s) => ({
                  ...s,
                  state: "confirmed" as const,
                }))
              : undefined,
            toolCalls: m.tool_calls ?? undefined,
            plan: m.plan ?? undefined,
            isError: m.is_error ?? false,
            stopped: m.stopped ?? false,
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
          } else if (hasAttachments) {
            // Attachments are present, so the reply is likely still reading them.
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
            isPending: true,
          });
        }

        setHistoryState({
          loading: false,
          messages: loaded.length ? loaded : [WELCOME_MESSAGE],
        });

        // Older conversations stored each upload as a message; newer ones list theirs from the server.
        const sentUploads: TextAttachment[] = transcript.flatMap((m) =>
          m.message_type === "attachment" && m.attachment_name
            ? [
                {
                  name: m.attachment_name,
                  size: m.attachment_size ?? 0,
                  uploadId: `message-${m.id}`,
                  isSent: true,
                  isStoredInMessage: true,
                },
              ]
            : [],
        );
        const uploadedFileAttachments: TextAttachment[] = uploadedFiles.map((file) => ({
          name: file.name,
          size: file.size,
          uploadId: `uploaded-${file.name}`,
          isSent: true,
        }));
        setInputAttachments([
          ...persistedFiles.map((f) => ({
            name: f.name,
            size: f.size ?? 0,
            documentId: f.id,
            source: f.source ?? undefined,
          })),
          ...sentUploads,
          ...uploadedFileAttachments,
        ]);
      } catch (err) {
        // A failure from a load already superseded by another chat says nothing about that chat.
        if (signal.aborted) return;
        console.error(err);
        setLoadError(getLoadError(err));
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

    const controller = new AbortController();

    const intervalId = setInterval(async () => {
      if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
        clearInterval(intervalId);
        clearStreamProgress(conversationId);
        setMessages((prev) =>
          prev.map((m) =>
            RECOVERY_PLACEHOLDER_IDS.has(m.id)
              ? {
                  ...m,
                  content: "The response could not be recovered. Please try again.",
                  isError: true,
                  isPending: false,
                }
              : m,
          ),
        );
        return;
      }
      try {
        const lastApiMsg = await getLastMessage(token, conversationId, controller.signal);
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
                ? lastApiMsg.rag_sections.map((s) => ({
                    ...s,
                    state: "confirmed" as const,
                  }))
                : undefined,
              toolCalls: lastApiMsg.tool_calls ?? undefined,
              plan: lastApiMsg.plan ?? undefined,
              isError: lastApiMsg.is_error ?? false,
              stopped: lastApiMsg.stopped ?? false,
            },
          ];
        });
        clearInterval(intervalId);
      } catch {
        // network error or abort — will retry on next tick (or cleanup already ran)
      }
    }, POLL_INTERVAL_MS);

    return () => {
      clearInterval(intervalId);
      controller.abort();
    };
  }, [hasPendingPlaceholder, conversationId, token, setMessages]);

  return {
    loading: historyState.loading,
    messages: historyState.messages,
    loadError,
    error,
    setError,
    inputMessage,
    setInputMessage,
    inputAttachments,
    setInputAttachments,
    setMessages,
    clearError: () => setError(null),
    skipNextLoadRef,
  };
}
