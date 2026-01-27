import { FileText, X } from "lucide-react";
import { TextAttachment } from "../../types";

interface PillProps {
  attachment: TextAttachment | null;
  onOpen: () => void;
  onRemove?: () => void;
}

export function Pill({ attachment, onOpen, onRemove }: PillProps) {
  if (!attachment) return null;

  return (
    <div className="flex items-center justify-between bg-surface-variant px-3 py-2 rounded-lg text-sm">
      <button
        onClick={onOpen}
        className="flex items-center gap-2 text-foreground hover:underline hover:cursor-pointer"
      >
        <FileText className="w-4 h-4" />
        <span className="truncate">{attachment.name}</span>
      </button>

      {onRemove && (
        <button
          onClick={onRemove}
          className="text-muted-foreground hover:text-foreground hover:cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
