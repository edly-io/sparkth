import { FileText, X } from "lucide-react";
import { TextAttachment } from "../../types";
import { Button } from "@/components/ui/Button";

interface PillProps {
  attachment: TextAttachment | null;
  onOpen: () => void;
  onRemove?: () => void;
}

export function Pill({ attachment, onOpen, onRemove }: PillProps) {
  if (!attachment) return null;

  return (
    <div className="flex items-center justify-between bg-surface-variant px-3 py-2 rounded-lg text-sm">
      <Button
        variant="ghost"
        size="sm"
        onClick={onOpen}
        className="flex items-center gap-2 text-foreground hover:underline p-0 h-auto"
      >
        <FileText className="w-4 h-4" />
        <span className="truncate">{attachment.name}</span>
      </Button>

      {onRemove && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onRemove}
          className="text-muted-foreground hover:text-foreground p-0 h-auto"
        >
          <X className="w-4 h-4" />
        </Button>
      )}
    </div>
  );
}
