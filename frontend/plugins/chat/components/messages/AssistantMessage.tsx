import { AlertCircle, Bot } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { ChatMessage, TextAttachment } from "../../types";
import { Pill } from "../attachment/Pill";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function ThinkingDots() {
  return (
    <div className="flex items-center gap-1 py-1">
      <span className="w-2 h-2 rounded-full bg-neutral-400 dark:bg-neutral-500 animate-bounce [animation-delay:0ms]" />
      <span className="w-2 h-2 rounded-full bg-neutral-400 dark:bg-neutral-500 animate-bounce [animation-delay:150ms]" />
      <span className="w-2 h-2 rounded-full bg-neutral-400 dark:bg-neutral-500 animate-bounce [animation-delay:300ms]" />
    </div>
  );
}

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
  const isThinking = message.isTyping && !displayText;

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

      <div className="max-w-[75%] w-fit space-y-2">
        {/* RAG context indicator — outside bubble, persistent */}
        {message.ragSections && message.ragSections.length > 0 && (
          <div className="px-1 space-y-0.5">
            <p className="text-xs text-neutral-400 dark:text-neutral-500">Taking into context:</p>
            <ul className="space-y-0.5">
              {message.ragSections.slice(0, 5).map((section, i) => (
                <li
                  key={i}
                  className="text-xs text-neutral-400 dark:text-neutral-500 flex items-baseline gap-1.5"
                >
                  {section.state === "scanning" ? (
                    <span className="w-1.5 h-1.5 rounded-full bg-neutral-300 dark:bg-neutral-600 flex-shrink-0 mt-0.5 animate-pulse" />
                  ) : (
                    <span className="w-1 h-1 rounded-full bg-neutral-300 dark:bg-neutral-600 flex-shrink-0 mt-1" />
                  )}
                  <span className="capitalize">{section.type}</span>
                  <span className="text-neutral-300 dark:text-neutral-600">—</span>
                  <span className={section.state === "scanning" ? "opacity-50" : ""}>
                    {section.name}
                  </span>
                </li>
              ))}
              {message.ragSections.length > 5 && (
                <li className="relative group ml-2.5 w-fit">
                  <span className="text-xs text-neutral-300 dark:text-neutral-600 cursor-default underline decoration-dotted">
                    +{message.ragSections.length - 5} more
                  </span>
                  {/* Hover tooltip showing remaining sections */}
                  <div className="absolute bottom-full left-0 mb-1.5 hidden group-hover:block z-20 bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-700 rounded-md shadow-lg p-2 min-w-max max-w-xs">
                    <ul className="space-y-1">
                      {message.ragSections.slice(5).map((section, i) => (
                        <li
                          key={i}
                          className="text-xs text-neutral-500 dark:text-neutral-400 flex items-baseline gap-1.5"
                        >
                          <span className="w-1 h-1 rounded-full bg-neutral-300 dark:bg-neutral-600 flex-shrink-0 mt-1" />
                          <span className="capitalize">{section.type}</span>
                          <span className="text-neutral-300 dark:text-neutral-600">—</span>
                          <span>{section.name}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </li>
              )}
            </ul>
          </div>
        )}

        {message.isError ? (
          <Card variant="outlined" className="p-4 border-error bg-error-50">
            <div className="flex items-start gap-2 text-error-500">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <p className="text-sm">{displayText || "Something went wrong. Please try again."}</p>
            </div>
          </Card>
        ) : (
          <Card variant="outlined" className="p-4">
            {isThinking ? (
              message.statusText ? (
                <div className="flex items-center gap-2 py-1">
                  <span className="w-2 h-2 rounded-full bg-neutral-400 dark:bg-neutral-500 animate-pulse" />
                  <p className="text-sm text-muted-foreground">{message.statusText}</p>
                </div>
              ) : (
                <ThinkingDots />
              )
            ) : (
              <div className="prose prose-neutral dark:prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayText}</ReactMarkdown>
              </div>
            )}

            {!message.isTyping && (
              <Pill attachment={message.pillAttachment ?? null} onOpen={openPreview} />
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
