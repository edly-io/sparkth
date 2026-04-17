"use client";

import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ChatHeader } from "./components/ChatHeader";
import { ChatMessages } from "./components/messages/ChatMessages";
import { ChatInput } from "./components/input/ChatInput";
import { ChatMessage, TextAttachment } from "./types";
import { Preview } from "./components/attachment/Preview";
import { useAuth } from "@/lib/auth-context";
import { usePlugin } from "@/lib/plugins/context";
import { Alert } from "@/components/ui/Alert";

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

export default function ChatInterface() {
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
  const [error, setError] = useState<string | null>(null);
  const [inputAttachment, setInputAttachment] = useState<TextAttachment | null>(null);
  const [previewAttachment, setPreviewAttachment] = useState<TextAttachment | null>(null);
  const [historyState, setHistoryState] = useState<{
    loading: boolean;
    messages: ChatMessage[];
  }>({
    loading: !!conversationId,
    messages: conversationId ? [] : [WELCOME_MESSAGE],
  });

  const { loading: loadingHistory, messages } = historyState;

  const setMessages = (updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) =>
    setHistoryState((prev) => ({
      ...prev,
      messages: typeof updater === "function" ? updater(prev.messages) : updater,
    }));

  useEffect(() => {
    let cancelled = false;
    const loadConversation = async () => {
      if (!conversationId) {
        setHistoryState({
          loading: false,
          messages: [WELCOME_MESSAGE],
        });
        return;
      }

      setHistoryState({
        loading: true,
        messages: [],
      });
      fetch(`/api/v1/chat/conversations/${conversationId}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((r) => {
          if (!r.ok) throw new Error(`Load conversation failed with status ${r.status}`);
          return r.json();
        })
        .then((data: ApiConversation) => {
          if (cancelled) return;
          const loaded: ChatMessage[] = data.messages.map((m) => ({
            id: String(m.id),
            role: m.role,
            content: m.message_type === "attachment" ? "" : m.content,
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

          // Restore persistent drive file attachment
          if (data.active_drive_file_id && data.active_drive_file_name) {
            setInputAttachment({
              name: data.active_drive_file_name,
              size: 0,
              text: `[File: ${data.active_drive_file_name}]`,
              driveFileDbId: data.active_drive_file_id,
            });
          }
        })
        .catch((e) => {
          if (cancelled) return;
          console.error(e);
          setError("Failed to load conversation. Please try again.");
          setHistoryState({
            loading: false,
            messages: [WELCOME_MESSAGE],
          });
        });
    };
    loadConversation();
    return () => {
      cancelled = true;
    };
  }, [conversationId, token]);

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
  }: {
    message: string;
    attachment: TextAttachment | null;
  }) => {
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

            if (parsed.token) {
              assistantText += parsed.token;
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantId ? { ...msg, streamedContent: assistantText } : msg,
                ),
              );
            }

            if (parsed.done) {
              if (parsed.conversation_id) {
                newConversationId = String(parsed.conversation_id);
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
                }
              : msg,
          ),
        );

        if (!conversationId && newConversationId) {
          router.replace(`/dashboard/chat?id=${newConversationId}`);
        }
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Something went wrong.";
      failAssistantMessage(assistantId, errorMsg);
    }
  };

  const handleSetAttachment = (attachment: TextAttachment | null) => {
    setInputAttachment(attachment);
    // If clearing (null) and there's an active drive file, clear on backend too
    if (attachment === null && conversationId && inputAttachment?.driveFileDbId) {
      fetch(`/api/v1/chat/conversations/${conversationId}/active-file`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {});
    }
  };

  return (
    <div className="flex flex-col h-full bg-background transition-colors">
      <ChatHeader />
      {error && (
        <div className="px-4 pt-4">
          <Alert severity="error" title="Something went wrong" onClose={() => setError(null)}>
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
