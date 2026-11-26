import { useCallback, useRef, useState } from "react";
import { requestChatCompletionStream, stopChatTurn } from "@/plugins/compose/src/client";
import {
  ChatMessage,
  PlanSnapshot,
  StreamStatusEvent,
  StreamStatusPhase,
  TextAttachment,
  ToolCall,
} from "@/plugins/compose/src/types";

interface SendPayload {
  message: string;
  attachments: TextAttachment[];
  documentIds?: number[];
}

interface UseChatStreamOptions {
  token: string | null;
  llmConfigId: number | undefined;
  modelOverride?: string | null;
  conversationId: string | null;
  setMessages: (updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => void;
  onNewConversation: (id: string) => void;
}

function applyStatusEvent(
  event: StreamStatusEvent,
  assistantId: string,
  setMessages: UseChatStreamOptions["setMessages"],
) {
  const update = (change: (msg: ChatMessage) => ChatMessage) =>
    setMessages((prev) => prev.map((msg) => (msg.id === assistantId ? change(msg) : msg)));

  switch (event.status) {
    case "scanning_section": {
      const { section } = event;
      update((msg) => ({
        ...msg,
        statusPhase: undefined,
        ragSections: [...(msg.ragSections ?? []), { ...section, state: "scanning" }],
      }));
      break;
    }
    case "section_confirmed": {
      const { name } = event.section;
      update((msg) => ({
        ...msg,
        ragSections: msg.ragSections?.map((s) =>
          s.name === name ? { ...s, state: "confirmed" } : s,
        ),
      }));
      break;
    }
    case "scanning_attachments":
    case "searching_documents":
    case "skipping_rag":
    case "generating": {
      const { status } = event;
      update((msg) => ({ ...msg, statusPhase: status }));
      break;
    }
    case "step": {
      const stepLabel = event.step_status;
      update((msg) => ({ ...msg, stepLabel }));
      break;
    }
    case "plan": {
      const { plan } = event;
      update((msg) => ({ ...msg, plan }));
      break;
    }
    case "tool_call": {
      const { tool_name: toolName, tool_status: toolStatus } = event;
      update((msg) => {
        const existing = msg.toolCalls ?? [];
        if (toolStatus === "running") {
          return { ...msg, toolCalls: [...existing, { name: toolName, status: "running" }] };
        }
        // TODO: tool_end events are matched by name alone; if the same tool is
        // called in parallel, the first running entry wins regardless of which
        // invocation actually finished. Fix by tracking a unique call ID instead.
        let marked = false;
        const updated = existing.map((t) => {
          if (!marked && t.name === toolName && t.status === "running") {
            marked = true;
            return { ...t, status: toolStatus };
          }
          return t;
        });
        return { ...msg, toolCalls: updated };
      });
      break;
    }
    default:
      // A status the API does not declare is ignored; one it declares must be handled above.
      event satisfies never;
  }
}

const STREAM_STORAGE_KEY = (conversationId: string) => `chat_stream:${conversationId}`;
const STREAM_STORAGE_TTL_MS = 5 * 60 * 1000; // 5 minutes
// Stay safely under the typical 5 MB sessionStorage limit. Writes are skipped
// once the payload exceeds this — recovery degrades gracefully for very long
// responses rather than throwing QuotaExceededError silently.
const STREAM_STORAGE_MAX_BYTES = 4 * 1024 * 1024;

function saveStreamProgress(
  conversationId: string | null,
  content: string,
  phase?: StreamStatusPhase,
): void {
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
  phase?: StreamStatusPhase;
}

export function getRestoredStreamData(conversationId: string): StreamProgressData | null {
  try {
    const raw = sessionStorage.getItem(STREAM_STORAGE_KEY(conversationId));
    if (!raw) return null;
    const { content, phase, timestamp } = JSON.parse(raw) as {
      content: string;
      phase?: StreamStatusPhase;
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
  let doneRagSections: { type: string; name: string; source?: string }[] | null = null;
  let doneToolCalls: ToolCall[] | null = null;
  let doneStopped = false;
  let finalPlan: PlanSnapshot | null = null;
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
          const event = parsed as StreamStatusEvent;
          if (event.status === "scanning_attachments" || event.status === "searching_documents") {
            saveStreamProgress(conversationId, assistantText, event.status);
          }
          applyStatusEvent(event, assistantId, setMessages);
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
                    statusPhase: undefined,
                  }
                : msg,
            ),
          );
        }

        if (parsed.done) {
          if (parsed.conversation_id) newConversationId = String(parsed.conversation_id);
          if (parsed.content) assistantText = parsed.content;
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
            doneToolCalls = toolCallsFromDone as ToolCall[];
          }
          finalPlan = ((parsed.message as Record<string, unknown> | undefined)?.plan ??
            null) as PlanSnapshot | null;
          doneStopped = parsed.stopped === true;
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
    doneRagSections,
    doneToolCalls,
    doneStopped,
    finalPlan,
  };
}

/**
 * Sends a message and streams the reply into the conversation.
 *
 * One turn runs per conversation at a time: `handleSend` does nothing while `isTurnLive()` is
 * true, which it is from the moment a send starts until its reply ends. A turn in another
 * conversation does not block this one.
 */
export function useChatStream({
  token,
  llmConfigId,
  modelOverride,
  conversationId,
  setMessages,
  onNewConversation,
}: UseChatStreamOptions) {
  // The backend only notices a stop between provider events, so the button has to say it heard.
  const [isStopping, setIsStopping] = useState(false);
  // A ref, not state: sends fired before the next render must all see the turn that just started.
  const liveTurnRef = useRef<{ turnId: string; conversationId: string | null } | null>(null);

  const isTurnLive = useCallback(
    () => liveTurnRef.current !== null && liveTurnRef.current.conversationId === conversationId,
    [conversationId],
  );

  // A failure after text was written keeps that text as a reply of its own and shows the error
  // after it, as the server stores them.
  const failAssistantMessage = useCallback(
    (id: string, errorText: string) => {
      setMessages((prev) =>
        prev.flatMap((msg) => {
          if (msg.id !== id) return [msg];
          const ended = {
            ...msg,
            streamedContent: undefined,
            isTyping: false,
            isPending: false,
            statusPhase: undefined,
            stepLabel: undefined,
            toolCalls: msg.toolCalls?.map((tool) =>
              tool.status === "running" ? { ...tool, status: "done" as const } : tool,
            ),
          };
          if (!msg.streamedContent) return [{ ...ended, content: errorText, isError: true }];
          return [
            { ...ended, content: msg.streamedContent },
            { id: `${id}-error`, role: "assistant" as const, content: errorText, isError: true },
          ];
        }),
      );
    },
    [setMessages],
  );

  const handleSend = useCallback(
    async ({ message, attachments, documentIds }: SendPayload) => {
      if (isTurnLive()) return;
      const turnId = crypto.randomUUID();
      liveTurnRef.current = { turnId, conversationId };
      setIsStopping(false);

      // Strip recovery placeholders before starting a fresh stream — prevents the
      // post-refresh polling from conflicting with a new, live stream.
      setMessages((prev) => prev.filter((m) => !RECOVERY_PLACEHOLDER_IDS.has(m.id)));

      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: message,
        attachments,
      };
      setMessages((prev) => [...prev, userMessage]);

      // A file goes to the server once, with this message; the server keeps it for the later ones.
      const files = attachments.flatMap(({ name, text }) =>
        text === undefined ? [] : [{ name, text }],
      );
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
        const res = await requestChatCompletionStream(token, {
          // Callers run the AI-key guard first; if it is still undefined, the backend 422s and
          // the catch below surfaces its message.
          llm_config_id: llmConfigId as number,
          ...(modelOverride && { model_override: modelOverride }),
          messages: [{ role: "user", content: message }],
          ...(files.length > 0 && { files }),
          stream: true,
          temperature: 0.7,
          tools: "*",
          turn_id: turnId,
          ...(conversationId && { conversation_id: conversationId }),
          ...(documentIds && documentIds.length > 0 && { document_ids: documentIds }),
        });

        if (!res.body) {
          failAssistantMessage(assistantId, "No response body received.");
          return;
        }

        const {
          assistantText,
          newConversationId,
          hasError,
          doneRagSections,
          doneToolCalls,
          doneStopped,
          finalPlan,
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
                    statusPhase: undefined,
                    stepLabel: undefined,
                    ...(finalPlan && { plan: finalPlan }),
                    ...(doneRagSections && {
                      ragSections: doneRagSections.map((s) => ({
                        ...s,
                        state: "confirmed" as const,
                      })),
                    }),
                    ...(doneToolCalls && { toolCalls: doneToolCalls }),
                    ...(doneStopped && { stopped: true }),
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
        // ApiRequestError extends Error, so its message — the API's own text — flows straight
        // through; the guard now catches the no-key case before a request is ever made.
        const errorMsg = err instanceof Error ? err.message : "Something went wrong.";
        failAssistantMessage(assistantId, errorMsg);
      } finally {
        // A turn started since, in another conversation, stays live.
        if (liveTurnRef.current?.turnId === turnId) {
          liveTurnRef.current = null;
          setIsStopping(false);
        }
      }
    },
    [
      token,
      llmConfigId,
      modelOverride,
      conversationId,
      setMessages,
      isTurnLive,
      failAssistantMessage,
      onNewConversation,
    ],
  );

  const stopGeneration = useCallback(async () => {
    const turnId = liveTurnRef.current?.turnId;
    if (!turnId) return;
    setIsStopping(true);
    await stopChatTurn(token, turnId).catch((err) =>
      console.error("Failed to stop chat turn:", err),
    );
  }, [token]);

  return { handleSend, stopGeneration, isStopping, isTurnLive };
}
