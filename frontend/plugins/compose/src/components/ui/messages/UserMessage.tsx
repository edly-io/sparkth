import { ChatMessage } from "@/plugins/compose/src/types";

interface UserMessageProps {
  message: ChatMessage;
}

/** A message the user sent, showing only the text they typed. */
export function UserMessage({ message }: UserMessageProps) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[75%]">
        {message.content && (
          <div className="rounded-xl bg-foreground text-background px-4 py-2 text-sm whitespace-pre-wrap">
            {message.content}
          </div>
        )}
      </div>
    </div>
  );
}
