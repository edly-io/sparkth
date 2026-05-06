import { useCallback, useRef } from "react";
import { ChatMessage, TextAttachment } from "../types";

interface SendPayload {
  message: string;
  attachments: TextAttachment[];
  similarityThreshold?: number;
}

interface UseChatStreamOptions {
  token: string | null;
  provider: string | undefined;
  model: string | undefined;
  conversationId: string | null;
  setMessages: (updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => void;
  onNewConversation: (id: string) => void;
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
    if (attachment.driveFileDbId !== undefined) {
      const contentBlocks: object[] = [{ type: "drive_file", file_id: attachment.driveFileDbId }];
      if (isLast && message.trim()) contentBlocks.push({ type: "text", text: message });
      out.push({
        role: "user",
        content: contentBlocks,
        attachment: { name: attachment.name, size: attachment.size },
      });
    } else if (attachment.base64Data) {
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
    const section = parsed.section as { type: string; name: string; source?: string };
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
  }
}

async function readStream(
  body: ReadableStream<Uint8Array>,
  assistantId: string,
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

        if (parsed.error) {
          onFail(parsed.error ?? "An error occurred.");
          hasError = true;
          break outer;
        }

        if (parsed.status) {
          applyStatusEvent(parsed, assistantId, setMessages);
          continue;
        }

        if (parsed.token) {
          assistantText += parsed.token;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? { ...msg, streamedContent: assistantText, statusText: undefined }
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
            doneRagSections = sections as { type: string; name: string; source?: string }[];
          }
          break outer;
        }
      } catch {
        console.error("Failed to parse SSE payload:", payload);
      }
    }
  }

  return { assistantText, newConversationId, hasError, doneOptions, doneRagSections };
}

export function useChatStream({
  token,
  provider,
  model,
  conversationId,
  setMessages,
  onNewConversation,
}: UseChatStreamOptions) {
  const lastSentRef = useRef<{ message: string; attachments: TextAttachment[] }>({
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
              }
            : msg,
        ),
      );
    },
    [setMessages],
  );

  const handleSend = useCallback(
    async ({ message, attachments, similarityThreshold = 0.45 }: SendPayload) => {
      lastSentRef.current = { message, attachments };
      lastSentThresholdRef.current = similarityThreshold;

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
        { id: assistantId, role: "assistant", content: "", streamedContent: "", isTyping: true },
      ]);

      try {
        const res = await fetch("/api/v1/chat/completions", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            provider,
            model,
            messages: newUserMessages,
            stream: true,
            tools: "*",
            tool_choice: "auto",
            include_system_tools_message: true,
            similarity_threshold: similarityThreshold,
            ...(conversationId && { conversation_id: conversationId }),
          }),
        });

        if (!res.ok) {
          failAssistantMessage(assistantId, "Something went wrong. Try again.");
          return;
        }
        if (!res.body) {
          failAssistantMessage(assistantId, "No response body received.");
          return;
        }

        const { assistantText, newConversationId, hasError, doneOptions, doneRagSections } =
          await readStream(res.body, assistantId, setMessages, (text) =>
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
                  }
                : msg,
            ),
          );

          if (!conversationId && newConversationId) {
            onNewConversation(newConversationId);
          }
        }
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "Something went wrong.";
        failAssistantMessage(assistantId, errorMsg);
      }
    },
    [token, provider, model, conversationId, setMessages, failAssistantMessage, onNewConversation],
  );

  const handleOptionClick = useCallback(
    (text: string) => {
      if (text === "Try with less strict matching") {
        const { message, attachments } = lastSentRef.current;
        const last = lastSentThresholdRef.current;
        const nextThreshold = last > 0.3 ? 0.3 : 0.15;
        handleSend({ message, attachments, similarityThreshold: nextThreshold });
      } else {
        handleSend({ message: text, attachments: [] });
      }
    },
    [handleSend],
  );

  return { handleSend, handleOptionClick };
}
