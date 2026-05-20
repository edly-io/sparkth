import { useCallback, useRef } from "react";
import { ChatMessage, TextAttachment } from "../types";

interface SendPayload {
  message: string;
  attachments: TextAttachment[];
  driveFileIds?: number[];
  similarityThreshold?: number;
}

interface UseChatStreamOptions {
  token: string | null;
  llmConfigId: number | undefined;
  modelOverride?: string | null;
  conversationId: string | null;
  setMessages: (updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => void;
  onNewConversation: (id: string) => void;
}

interface ValidationErrorItem {
  type: string;
  loc: (string | number)[];
  msg: string;
}

const FIELD_MESSAGES: Record<string, string> = {
  llm_config_id: "No AI Key selected. Go to chat settings to configure one.",
};

function extractValidationError(detail: ValidationErrorItem[]): string {
  for (const item of detail) {
    const field = item.loc.find((part) => typeof part === "string" && part !== "body");
    if (field && typeof field === "string" && FIELD_MESSAGES[field]) {
      return FIELD_MESSAGES[field];
    }
  }
  return "Something went wrong. Try again.";
}

function buildUserMessages(message: string, attachments: TextAttachment[]) {
  const out: Array<{
    role: string;
    content: string | object[];
    attachment?: { name: string; size: number };
  }> = [];

  for (let i = 0; i < attachments.length; i++) {
    const attachment = attachments[i];
    const isLast = i === attachments.length - 1;
    if (attachment.base64Data) {
      const contentBlocks: object[] = [
        {
          type: "document",
          source: {
            type: "base64",
            media_type: attachment.mediaType || "application/pdf",
            data: attachment.base64Data,
          },
        },
      ];
      if (isLast && message.trim()) contentBlocks.push({ type: "text", text: message });
      out.push({
        role: "user",
        content: contentBlocks,
        attachment: { name: attachment.name, size: attachment.size },
      });
    } else {
      if (attachment.text) {
        const content =
          isLast && message.trim() ? `${message}\n\n---\n\n${attachment.text}` : attachment.text;
        out.push({
          role: "user",
          content,
          attachment: { name: attachment.name, size: attachment.size },
        });
      }
    }
  }

  if (message.trim() && out.length === 0) {
    out.push({ role: "user", content: message });
  }

  return out;
}

function applyStatusEvent(
  parsed: Record<string, unknown>,
  assistantId: string,
  setMessages: UseChatStreamOptions["setMessages"],
) {
  if (parsed.status === "section_scanning" && parsed.section) {
    const section = parsed.section as {
      type: string;
      name: string;
      source?: string;
    };
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === assistantId
          ? {
              ...msg,
              statusText: undefined,
              ragSections: [...(msg.ragSections ?? []), { ...section, state: "scanning" as const }],
            }
          : msg,
      ),
    );
  } else if (parsed.status === "section_confirmed" && parsed.section) {
    const sectionName = (parsed.section as { name: string }).name;
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === assistantId
          ? {
              ...msg,
              ragSections: msg.ragSections?.map((s) =>
                s.name === sectionName ? { ...s, state: "confirmed" as const } : s,
              ),
            }
          : msg,
      ),
    );
  } else if (parsed.status === "section_removed" && parsed.section) {
    const sectionName = (parsed.section as { name: string }).name;
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === assistantId
          ? {
              ...msg,
              ragSections: (msg.ragSections ?? []).filter((s) => s.name !== sectionName),
            }
          : msg,
      ),
    );
  } else if (parsed.status === "searching_document") {
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === assistantId ? { ...msg, statusText: "Scanning document sections..." } : msg,
      ),
    );
  } else if (parsed.status === "tool_call" && parsed.tool_name) {
    const toolName = parsed.tool_name as string;
    const toolStatus = parsed.tool_status as "running" | "done";
    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id !== assistantId) return msg;
        const existing = msg.toolCalls ?? [];
        if (toolStatus === "running") {
          return {
            ...msg,
            toolCalls: [...existing, { name: toolName, status: "running" as const }],
          };
        }
        // TODO: tool_end events are matched by name alone; if the same tool is
        // called in parallel, the first running entry wins regardless of which
        // invocation actually finished. Fix by tracking a unique call ID instead.
        let marked = false;
        const updated = existing.map((t) => {
          if (!marked && t.name === toolName && t.status === "running") {
            marked = true;
            return { ...t, status: "done" as const };
          }
          return t;
        });
        return { ...msg, toolCalls: updated };
      }),
    );
  }
}

const STREAM_STORAGE_KEY = (conversationId: string) => `chat_stream:${conversationId}`;
const STREAM_STORAGE_TTL_MS = 5 * 60 * 1000; // 5 minutes
// Stay safely under the typical 5 MB sessionStorage limit. Writes are skipped
// once the payload exceeds this — recovery degrades gracefully for very long
// responses rather than throwing QuotaExceededError silently.
const STREAM_STORAGE_MAX_BYTES = 4 * 1024 * 1024;

function saveStreamProgress(conversationId: string | null, content: string, phase?: string): void {
  if (!conversationId) return;
  try {
    const payload = JSON.stringify({ content, phase, timestamp: Date.now() });
    if (payload.length > STREAM_STORAGE_MAX_BYTES) return;
    sessionStorage.setItem(STREAM_STORAGE_KEY(conversationId), payload);
  } catch {
    // sessionStorage unavailable (private browsing) — silently ignore
  }
}

export function clearStreamProgress(conversationId: string | null): void {
  if (!conversationId) return;
  try {
    sessionStorage.removeItem(STREAM_STORAGE_KEY(conversationId));
  } catch {
    // ignore
  }
}

// Synthetic message IDs injected by useConversation when a response is pending after refresh.
// handleSend strips these before starting a new stream so polling and streaming don't conflict.
export const RECOVERY_PLACEHOLDER_IDS = new Set(["restored-stream", "pending-response"]);

export interface StreamProgressData {
  content: string;
  phase?: string;
}

export function getRestoredStreamData(conversationId: string): StreamProgressData | null {
  try {
    const raw = sessionStorage.getItem(STREAM_STORAGE_KEY(conversationId));
    if (!raw) return null;
    const { content, phase, timestamp } = JSON.parse(raw) as {
      content: string;
      phase?: string;
      timestamp: number;
    };
    if (Date.now() - timestamp > STREAM_STORAGE_TTL_MS) return null;
    // Return even if content is empty — phase alone (e.g. "scanning") is useful for UX.
    if (!content && !phase) return null;
    return { content, phase };
  } catch {
    return null;
  }
}

async function readStream(
  body: ReadableStream<Uint8Array>,
  assistantId: string,
  conversationId: string | null,
  setMessages: UseChatStreamOptions["setMessages"],
  onFail: (text: string) => void,
) {
  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8");
  let assistantText = "";
  let buffer = "";
  let newConversationId: string | null = null;
  let hasError = false;
  let doneOptions: string[] = [];
  let doneRagSections: { type: string; name: string; source?: string }[] | null = null;
  let doneToolCalls: { name: string }[] | null = null;
  let lastSaveTime = 0;
  const SAVE_INTERVAL_MS = 500;

  outer: while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) continue;
      const payload = trimmed.replace(/^data:\s*/, "");
      if (!payload) continue;

      try {
        const parsed = JSON.parse(payload);

        if (parsed.error !== undefined) {
          onFail(parsed.error || "An error occurred.");
          hasError = true;
          break outer;
        }

        if (parsed.status) {
          // Persist the current RAG phase so a mid-stream refresh can show a
          // meaningful message ("Scanning documents…") rather than a generic one.
          if (parsed.status === "scanning_attachments" || parsed.status === "searching_document") {
            saveStreamProgress(conversationId, assistantText, parsed.status as string);
          }
          applyStatusEvent(parsed, assistantId, setMessages);
          continue;
        }

        if (parsed.token) {
          assistantText += parsed.token;
          const now = Date.now();
          if (now - lastSaveTime >= SAVE_INTERVAL_MS) {
            saveStreamProgress(conversationId, assistantText);
            lastSaveTime = now;
          }
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? {
                    ...msg,
                    streamedContent: assistantText,
                    statusText: undefined,
                  }
                : msg,
            ),
          );
        }

        if (parsed.done) {
          if (parsed.conversation_id) newConversationId = String(parsed.conversation_id);
          if (parsed.content) assistantText = parsed.content;
          if (parsed.options) doneOptions = parsed.options as string[];
          const sections = (parsed.message as Record<string, unknown> | undefined)?.rag_sections;
          if (Array.isArray(sections) && sections.length > 0) {
            doneRagSections = sections as {
              type: string;
              name: string;
              source?: string;
            }[];
          }
          const toolCallsFromDone = (parsed.message as Record<string, unknown> | undefined)
            ?.tool_calls;
          if (Array.isArray(toolCallsFromDone) && toolCallsFromDone.length > 0) {
            doneToolCalls = toolCallsFromDone as { name: string }[];
          }
          break outer;
        }
      } catch {
        console.error("Failed to parse SSE payload:", payload);
      }
    }
  }

  // Final flush: write all accumulated tokens before returning so a refresh in
  // the narrow gap between stream-end and DB commit still recovers the full text.
  // useConversation's polling clears the key once the DB message lands.
  saveStreamProgress(conversationId, assistantText);

  return {
    assistantText,
    newConversationId,
    hasError,
    doneOptions,
    doneRagSections,
    doneToolCalls,
  };
}

export function useChatStream({
  token,
  llmConfigId,
  modelOverride,
  conversationId,
  setMessages,
  onNewConversation,
}: UseChatStreamOptions) {
  const lastSentRef = useRef<{
    message: string;
    attachments: TextAttachment[];
  }>({
    message: "",
    attachments: [],
  });
  const lastSentThresholdRef = useRef<number>(0.45);

  const failAssistantMessage = useCallback(
    (id: string, errorText: string) => {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === id
            ? {
                ...msg,
                content: errorText,
                streamedContent: undefined,
                isTyping: false,
                isError: true,
                isPending: false,
              }
            : msg,
        ),
      );
    },
    [setMessages],
  );

  const handleSend = useCallback(
    async ({ message, attachments, driveFileIds, similarityThreshold = 0.45 }: SendPayload) => {
      lastSentRef.current = { message, attachments };
      lastSentThresholdRef.current = similarityThreshold;

      // Strip recovery placeholders before starting a fresh stream — prevents the
      // post-refresh polling from conflicting with a new, live stream.
      setMessages((prev) => prev.filter((m) => !RECOVERY_PLACEHOLDER_IDS.has(m.id)));

      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: message || (attachments.length > 0 ? "Uploaded a document" : ""),
        attachments,
      };
      setMessages((prev) => [...prev, userMessage]);

      const newUserMessages = buildUserMessages(message, attachments);
      const assistantId = crypto.randomUUID();

      setMessages((prev) => [
        ...prev,
        {
          id: assistantId,
          role: "assistant",
          content: "",
          streamedContent: "",
          isTyping: true,
        },
      ]);

      try {
        const res = await fetch("/api/v1/chat/completions", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            llm_config_id: llmConfigId,
            ...(modelOverride && { model_override: modelOverride }),
            messages: newUserMessages,
            stream: true,
            tools: "*",
            tool_choice: "auto",
            include_system_tools_message: true,
            similarity_threshold: similarityThreshold,
            ...(conversationId && { conversation_id: conversationId }),
            ...(driveFileIds && driveFileIds.length > 0 && { drive_file_ids: driveFileIds }),
          }),
        });

        if (!res.ok) {
          let errorMsg = "Something went wrong. Try again.";
          try {
            const errData = await res.json();
            if (errData?.detail && typeof errData.detail === "string") {
              errorMsg = errData.detail;
            } else if (Array.isArray(errData?.detail)) {
              errorMsg = extractValidationError(errData.detail);
            }
          } catch {
            // ignore parse errors, fall back to generic message
          }
          failAssistantMessage(assistantId, errorMsg);
          return;
        }
        if (!res.body) {
          failAssistantMessage(assistantId, "No response body received.");
          return;
        }

        const {
          assistantText,
          newConversationId,
          hasError,
          doneOptions,
          doneRagSections,
          doneToolCalls,
        } = await readStream(res.body, assistantId, conversationId, setMessages, (text) =>
          failAssistantMessage(assistantId, text),
        );

        if (!hasError) {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? {
                    ...msg,
                    content: assistantText,
                    streamedContent: undefined,
                    isTyping: false,
                    statusText: undefined,
                    ...(doneOptions.length > 0 && { options: doneOptions }),
                    ...(doneRagSections && {
                      ragSections: doneRagSections.map((s) => ({
                        ...s,
                        state: "confirmed" as const,
                      })),
                    }),
                    ...(doneToolCalls && {
                      toolCalls: doneToolCalls.map((t) => ({ ...t, status: "done" as const })),
                    }),
                  }
                : msg,
            ),
          );

          if (!conversationId && newConversationId) {
            onNewConversation(newConversationId);
          }
        }
      } catch (err) {
        clearStreamProgress(conversationId);
        const errorMsg = err instanceof Error ? err.message : "Something went wrong.";
        failAssistantMessage(assistantId, errorMsg);
      }
    },
    [
      token,
      llmConfigId,
      modelOverride,
      conversationId,
      setMessages,
      failAssistantMessage,
      onNewConversation,
    ],
  );

  const handleOptionClick = useCallback(
    (text: string) => {
      if (text === "Try with less strict matching") {
        const { message, attachments } = lastSentRef.current;
        const last = lastSentThresholdRef.current;
        const nextThreshold = last > 0.3 ? 0.3 : 0.15;
        handleSend({
          message,
          attachments,
          similarityThreshold: nextThreshold,
        });
      } else {
        handleSend({ message: text, attachments: [] });
      }
    },
    [handleSend],
  );

  return { handleSend, handleOptionClick };
}
