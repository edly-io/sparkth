import { ChatMessage, TextAttachment } from "../../types";
import { UserMessage } from "./UserMessage";
import { AssistantMessage } from "./AssistantMessage";

interface ChatMessagesProps {
  messages: ChatMessage[];
  setPreviewOpen: (open: boolean) => void;
  setPreviewAttachment: (attachment: TextAttachment | null) => void;
  onSend: (payload: {
    message: string;
    attachment: TextAttachment | null;
  }) => void;
}

export function ChatMessages({
  messages,
  setPreviewOpen,
  setPreviewAttachment,
  onSend,
}: ChatMessagesProps) {
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
            onOptionClick={(text) =>
              onSend({ message: text, attachment: null })
            }
          />
        ),
      )}
    </div>
  );
}
