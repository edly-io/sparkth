"use client";

import { Suspense, useState, useEffect, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ChatHeader } from "./components/ChatHeader";
import { ChatMessages } from "./components/messages/ChatMessages";
import { ChatInput } from "./components/input/ChatInput";
import { ChatMessage, TextAttachment } from "./types";
import { Preview } from "./components/attachment/Preview";
import { useAuth } from "@/lib/auth-context";
import { usePlugin } from "@/lib/plugins/context";
import { Alert } from "@/components/ui/Alert";
import { useConversation } from "./hooks/useConversation";

export default function ChatInterface() {
  return (
    <Suspense
      fallback={
        <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
          Loading…
        </div>
      }
    >
      <ChatInterfaceInner />
    </Suspense>
  );
}

function ChatInterfaceInner() {
  const { token } = useAuth();
  const { config: chatConfig } = usePlugin("chat");
  const [catalogDefaults, setCatalogDefaults] = useState<{
    provider: string;
    model: string;
  } | null>(null);

  useEffect(() => {
    if (!token) return;
    fetch("/api/v1/chat/providers", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.default_provider && data?.default_model) {
          setCatalogDefaults({ provider: data.default_provider, model: data.default_model });
        }
      })
      .catch(() => {});
  }, [token]);

  const provider = (chatConfig?.provider as string | undefined) ?? catalogDefaults?.provider;
  const model = (chatConfig?.model as string | undefined) ?? catalogDefaults?.model;
  const router = useRouter();
  const searchParams = useSearchParams();
  const conversationId = searchParams.get("id");
  const [previewOpen, setPreviewOpen] = useState(false);
  const lastSentRef = useRef<{ message: string; attachment: TextAttachment | null }>({
    message: "",
    attachment: null,
  });
  const lastSentThresholdRef = useRef<number>(0.45);
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

  const failAssistantMessage = (id: string, errorText: string) => {
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
  };

  const handleSend = async ({
    message,
    attachment,
    similarityThreshold = 0.45,
  }: {
    message: string;
    attachment: TextAttachment | null;
    similarityThreshold?: number;
  }) => {
    lastSentRef.current = { message, attachment };
    lastSentThresholdRef.current = similarityThreshold;

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: message || "Uploaded a document",
      attachment,
    };

    setMessages((prev) => [...prev, userMessage]);

    const newUserMessages: Array<{
      role: string;
      content: string | object[];
      attachment?: { name: string; size: number };
    }> = [];

    if (attachment?.driveFileDbId !== undefined) {
      // Drive file with RAG processing — send file_id for server-side retrieval
      const contentBlocks: object[] = [
        {
          type: "drive_file",
          file_id: attachment.driveFileDbId,
        },
      ];
      if (message.trim()) {
        contentBlocks.push({ type: "text", text: message });
      }
      newUserMessages.push({
        role: "user",
        content: contentBlocks,
        attachment: { name: attachment.name, size: attachment.size },
      });
    } else if (attachment?.base64Data) {
      // Legacy local file upload — send base64 directly to LLM
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
      if (message.trim()) {
        contentBlocks.push({ type: "text", text: message });
      }
      newUserMessages.push({
        role: "user",
        content: contentBlocks,
        attachment: { name: attachment.name, size: attachment.size },
      });
    } else {
      if (attachment?.text) {
        newUserMessages.push({
          role: "user",
          content: attachment.text,
          attachment: { name: attachment.name, size: attachment.size },
        });
      }
      if (message.trim()) {
        newUserMessages.push({
          role: "user",
          content: message,
        });
      }
    }

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

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let assistantText = "";
      let buffer = "";
      let newConversationId: string | null = null;
      let streamDone = false;
      let hasError = false;
      let doneOptions: string[] = [];

      while (true) {
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
              failAssistantMessage(assistantId, parsed.error ?? "An error occurred.");
              hasError = true;
              streamDone = true;
              break;
            }

            if (parsed.status) {
              if (parsed.status === "section_scanning" && parsed.section) {
                const section = parsed.section as { type: string; name: string };
                // Server emits scanning events 80ms apart — add immediately, no client stagger
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantId
                      ? {
                          ...msg,
                          statusText: undefined,
                          ragSections: [
                            ...(msg.ragSections ?? []),
                            { ...section, state: "scanning" as const },
                          ],
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
                          ragSections: (msg.ragSections ?? []).filter(
                            (s) => s.name !== sectionName,
                          ),
                        }
                      : msg,
                  ),
                );
              } else if (parsed.status === "searching_document") {
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantId
                      ? { ...msg, statusText: "Scanning document sections..." }
                      : msg,
                  ),
                );
              }
              // "generating" is intentionally ignored
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
              if (parsed.conversation_id) {
                newConversationId = String(parsed.conversation_id);
              }
              // done event may carry pre-built content (e.g. no RAG chunks found)
              if (parsed.content) {
                assistantText = parsed.content;
              }
              if (parsed.options) {
                doneOptions = parsed.options as string[];
              }
              streamDone = true;
              break;
            }
          } catch {
            console.error("Failed to parse SSE payload:", payload);
          }
        }

        if (streamDone) break;
      }

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
                }
              : msg,
          ),
        );

        if (!conversationId && newConversationId) {
          skipNextLoadRef.current = true;
          router.replace(`/dashboard/chat?id=${newConversationId}`);
        }
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Something went wrong.";
      failAssistantMessage(assistantId, errorMsg);
    }
  };

  const handleOptionClick = (text: string) => {
    if (text === "Try with less strict matching") {
      const { message, attachment } = lastSentRef.current;
      const last = lastSentThresholdRef.current;
      // Stepped threshold: 0.45 → 0.30 → 0.15
      const nextThreshold = last > 0.3 ? 0.3 : 0.15;
      handleSend({ message, attachment, similarityThreshold: nextThreshold });
    } else {
      handleSend({ message: text, attachment: null });
    }
  };

  const handleSetAttachment = (attachment: TextAttachment | null) => {
    setInputAttachment(attachment);
    // If clearing (null) and there's an active drive file, clear on backend too
    if (attachment === null && conversationId && inputAttachment?.driveFileDbId) {
      fetch(`/api/v1/chat/conversations/${conversationId}/active-file`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      }).catch((err) => console.warn("Failed to clear active drive file on backend:", err));
    }
  };

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
