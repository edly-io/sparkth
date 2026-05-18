import { useCallback, useEffect, useRef } from "react";
import { ChatMessage, TextAttachment } from "../../types";
import { UserMessage } from "./UserMessage";
import { AssistantMessage } from "./AssistantMessage";

interface ChatMessagesProps {
  messages: ChatMessage[];
  setPreviewOpen: (open: boolean) => void;
  setPreviewAttachment: (attachment: TextAttachment | null) => void;
  onSend: (payload: {
    message: string;
    attachments: TextAttachment[];
    driveFileIds?: number[];
  }) => void;
  onOptionClick?: (text: string) => void;
}

export function ChatMessages({
  messages,
  setPreviewOpen,
  setPreviewAttachment,
  onSend,
  onOptionClick,
}: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);

  const onScroll = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    isNearBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  }, []);

  // New message added or stream completed — always scroll smooth.
  const lastContent = messages[messages.length - 1]?.content;
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, lastContent]);

  // Per-token streaming — scroll instantly only if already near bottom.
  const lastStreamedContent = messages[messages.length - 1]?.streamedContent;
  useEffect(() => {
    if (lastStreamedContent && isNearBottomRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: "instant" });
    }
  }, [lastStreamedContent]);

  return (
    <div ref={containerRef} onScroll={onScroll} className="flex-1 overflow-y-auto p-6 space-y-6">
      {messages.map((msg) =>
        msg.role === "user" ? (
          <UserMessage
            key={msg.id}
            message={msg}
            setPreviewOpen={setPreviewOpen}
            setPreviewAttachment={setPreviewAttachment}
          />
        ) : (
          <AssistantMessage
            key={msg.id}
            message={msg}
            setPreviewOpen={setPreviewOpen}
            setPreviewAttachment={setPreviewAttachment}
            onOptionClick={onOptionClick ?? ((text) => onSend({ message: text, attachments: [] }))}
          />
        ),
      )}
      <div ref={bottomRef} />
    </div>
  );
}
