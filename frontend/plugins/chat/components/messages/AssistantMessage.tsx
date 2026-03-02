import { AlertCircle, Bot } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { ChatMessage, TextAttachment } from "../../types";
import { Pill } from "../attachment/Pill";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface AssistantMessageProps {
  message: ChatMessage;
  setPreviewOpen: (open: boolean) => void;
  setPreviewAttachment: (attachment: TextAttachment | null) => void;
  onOptionClick: (text: string) => void;
}

export function AssistantMessage({
  message,
  setPreviewOpen,
  setPreviewAttachment,
  onOptionClick,
}: AssistantMessageProps) {
  const displayText = message.streamedContent ?? message.content;

  const openPreview = () => {
    if (!message.pillAttachment) return;
    setPreviewAttachment(message.pillAttachment);
    setPreviewOpen(true);
  };

  return (
    <div className="flex gap-4">
      <div className="w-8 h-8 rounded-full bg-neutral-200 dark:bg-neutral-700 flex items-center justify-center flex-shrink-0">
        <Bot className="w-4 h-4" />
      </div>

      <div className="flex-1 max-w-[75%] space-y-2">
        {message.isError ? (
          <Card
            variant="outlined"
            className="p-4 border-destructive/40 bg-destructive/5"
          >
            <div className="flex items-start gap-2 text-destructive">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <p className="text-sm">
                {displayText || "Something went wrong. Please try again."}
              </p>
            </div>
          </Card>
        ) : (
          <Card variant="outlined" className="p-4">
            <div className="prose prose-neutral dark:prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {displayText}
              </ReactMarkdown>
            </div>

            {!message.isTyping && (
              <Pill
                attachment={message.pillAttachment ?? null}
                onOpen={openPreview}
              />
            )}

            {!message.isTyping && message.options && (
              <div className="mt-4 flex flex-wrap gap-2">
                {message.options.map((opt) => (
                  <Button
                    key={opt}
                    variant="ghost"
                    size="sm"
                    onClick={() => onOptionClick(opt)}
                    className="bg-surface-variant"
                  >
                    {opt}
                  </Button>
                ))}
              </div>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}
