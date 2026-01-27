import { ChatMessage, TextAttachment } from "../../types";
import { Pill } from "../attachment/Pill";

interface UserMessageProps {
  message: ChatMessage;
  setPreviewOpen: (open: boolean) => void;
  setPreviewAttachment: (attachment: TextAttachment | null) => void;
}

export function UserMessage({
  message,
  setPreviewOpen,
  setPreviewAttachment,
}: UserMessageProps) {
  const openPreview = () => {
    if (!message.attachment) return;
    setPreviewAttachment(message.attachment);
    setPreviewOpen(true);
  };

  return (
    <div className="flex justify-end">
      <div className="max-w-[75%] space-y-1">
        <Pill
          attachment={message.attachment ?? null}
          onOpen={openPreview}
        />

        {message.content && (
          <div className="rounded-xl bg-foreground text-background px-4 py-2 text-sm">
            {message.content}
          </div>
        )}
      </div>
    </div>
  );
}
