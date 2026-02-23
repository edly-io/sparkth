"use client";

import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ChatHeader } from "./components/ChatHeader";
import { ChatMessages } from "./components/messages/ChatMessages";
import { ChatInput } from "./components/input/ChatInput";
import { ChatMessage, TextAttachment } from "./types";
import { Preview } from "./components/attachment/Preview";
import { useAuth } from "@/lib/auth-context";

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
  id: number;
  messages: ApiMessage[];
}

export default function ChatInterface() {
  const { token } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const conversationId = searchParams.get("id");

  // const [messages, setMessages] = useState<ChatMessage[]>(
  //   conversationId ? [] : [WELCOME_MESSAGE],
  // );
  const [previewOpen, setPreviewOpen] = useState(false);
  const [inputAttachment, setInputAttachment] = useState<TextAttachment | null>(
    null,
  );
  const [previewAttachment, setPreviewAttachment] =
    useState<TextAttachment | null>(null);
  // const [loadingHistory, setLoadingHistory] = useState(false);

  const [historyState, setHistoryState] = useState<{
    loading: boolean;
    messages: ChatMessage[];
  }>({
    loading: !!conversationId,
    messages: conversationId ? [] : [WELCOME_MESSAGE],
  });

  const { loading: loadingHistory, messages } = historyState;

  const setMessages = (
    updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[]),
  ) =>
    setHistoryState((prev) => ({
      ...prev,
      messages:
        typeof updater === "function" ? updater(prev.messages) : updater,
    }));

  useEffect(() => {
    if (!conversationId) return;

    let cancelled = false;

    fetch(`/api/v1/chat/conversations/${conversationId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
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
      })
      .catch((e) => {
        if (!cancelled) {
          console.error(e);
          setHistoryState({ loading: false, messages: [WELCOME_MESSAGE] });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [conversationId, token]);

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

    const newUserMessages: Array<
      Pick<ChatMessage, "role" | "content"> & {
        attachment?: { name: string; size: number };
      }
    > = [];
    if (attachment?.text)
      newUserMessages.push({
        role: "user",
        content: attachment.text,
        attachment: { name: attachment.name, size: attachment.size },
      });
    if (message.trim())
      newUserMessages.push({ role: "user", content: message });

    const outgoingMessages = newUserMessages;
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

    const res = await fetch("/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        provider: "anthropic",
        model: "claude-sonnet-4-20250514",
        messages: outgoingMessages,
        stream: true,
        tools: "*",
        tool_choice: "auto",
        include_system_tools_message: true,
        ...(conversationId && { conversation_id: Number(conversationId) }),
      }),
    });

    if (!res.body) throw new Error("No response body for streaming");

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let assistantText = "";
    let buffer = "";
    let newConversationId: string | null = null;
    let streamDone = false;

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

          if (parsed.token) {
            assistantText += parsed.token;
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantId
                  ? { ...msg, streamedContent: assistantText }
                  : msg,
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
        } catch (err) {
          console.error("Failed to parse SSE payload:", payload, err);
        }
      }

      if (streamDone) break;
    }

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
  };

  return (
    <div className="flex flex-col h-full bg-background transition-colors">
      <ChatHeader />

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
        setAttachment={setInputAttachment}
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
