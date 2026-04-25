import { FileText, X } from "lucide-react";
import { TextAttachment } from "../../types";
import { Button } from "@/components/ui/Button";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/Tooltip";

interface PillProps {
  attachments: TextAttachment[];
  onPreview: (attachment: TextAttachment) => void;
  onRemove: (driveFileDbId?: number) => void;
}

export function Pill({ attachments, onPreview, onRemove }: PillProps) {
  if (attachments.length === 0) return null;

  const firstAttachment = attachments[0];
  const remainingCount = attachments.length - 1;
  const isSingleFile = attachments.length === 1;

  return (
    <div className="flex items-center gap-2 bg-surface-variant px-3 py-2 rounded-lg text-sm">
      <div className="flex items-center gap-1 min-w-0">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onPreview(firstAttachment)}
          className="flex items-center gap-2 text-foreground hover:underline p-0 h-auto"
        >
          <FileText className="w-4 h-4" />
          <span className="truncate">{firstAttachment.name}</span>
        </Button>

        {!isSingleFile && (
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="text-muted-foreground cursor-help whitespace-nowrap">
                + {remainingCount} {remainingCount === 1 ? "other" : "others"}
              </span>
            </TooltipTrigger>
            <TooltipContent side="top">
              <div className="space-y-1">
                {attachments.slice(1).map((attachment) => (
                  <div key={attachment.driveFileDbId || attachment.name}>
                    {attachment.name}
                  </div>
                ))}
              </div>
            </TooltipContent>
          </Tooltip>
        )}
      </div>

      <Button
        variant="ghost"
        size="sm"
        onClick={() => onRemove()}
        className="text-muted-foreground hover:text-foreground p-0 h-auto ml-auto flex-shrink-0"
      >
        <X className="w-4 h-4" />
      </Button>
    </div>
  );
}
