import { useEffect, useRef } from "react";
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

  const lastContent = messages[messages.length - 1]?.content;
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, lastContent]);

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
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
