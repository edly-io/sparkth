import { FileText, X } from "lucide-react";
import { TextAttachment } from "../../types";
import { Button } from "@/components/ui/Button";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/Tooltip";
import { truncate, RAG_DISPLAY_NAME_MAX_CHARS } from "@/lib/utils";

interface PillProps {
  attachments: TextAttachment[];
  onPreview: (attachment: TextAttachment) => void;
  onRemove?: (driveFileDbId?: number) => void;
}

export function Pill({ attachments, onPreview, onRemove }: PillProps) {
  if (attachments.length === 0) return null;

  const firstAttachment = attachments[0];
  const remainingCount = attachments.length - 1;
  const isSingleFile = attachments.length === 1;

  return (
    <div className="flex items-center gap-2 bg-surface-variant px-3 py-2 rounded-lg text-sm">
      {isSingleFile ? (
        // Single file: show filename + optional remove button
        <>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onPreview(firstAttachment)}
            className="flex items-center gap-2 text-foreground hover:underline p-0 h-auto"
          >
            <FileText className="w-4 h-4" />
            <span className="truncate">
              {truncate(firstAttachment.name, RAG_DISPLAY_NAME_MAX_CHARS)}
            </span>
          </Button>
          {onRemove && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onRemove(firstAttachment.driveFileDbId)}
              className="text-muted-foreground hover:text-foreground p-0 h-auto ml-auto flex-shrink-0"
              title="Remove attachment"
            >
              <X className="w-4 h-4" />
            </Button>
          )}
        </>
      ) : (
        // Multiple files: show first + counter, with expandable list
        <>
          <div className="flex items-center gap-1 min-w-0">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onPreview(firstAttachment)}
              className="flex items-center gap-2 text-foreground hover:underline p-0 h-auto"
            >
              <FileText className="w-4 h-4" />
              <span className="truncate">
                {truncate(firstAttachment.name, RAG_DISPLAY_NAME_MAX_CHARS)}
              </span>
            </Button>
            {onRemove && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onRemove(firstAttachment.driveFileDbId)}
                className="text-muted-foreground hover:text-foreground p-0 h-auto"
                title="Remove attachment"
              >
                <X className="w-3 h-3" />
              </Button>
            )}

            <Tooltip>
              <TooltipTrigger asChild>
                <span className="text-muted-foreground cursor-help whitespace-nowrap">
                  + {remainingCount} {remainingCount === 1 ? "other" : "others"}
                </span>
              </TooltipTrigger>
              <TooltipContent side="top">
                <div className="space-y-1">
                  {attachments.slice(1).map((attachment, index) => (
                    <div
                      key={attachment.driveFileDbId ?? `${attachment.name}-${index}`}
                      className="flex items-center justify-between gap-2"
                    >
                      <span>{truncate(attachment.name, RAG_DISPLAY_NAME_MAX_CHARS)}</span>
                      {onRemove && (
                        <button
                          onClick={() => onRemove(attachment.driveFileDbId)}
                          className="ml-2 text-muted-foreground hover:text-foreground"
                          title="Remove attachment"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </TooltipContent>
            </Tooltip>
          </div>

          {onRemove && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onRemove()}
              className="text-muted-foreground hover:text-foreground p-0 h-auto ml-auto flex-shrink-0"
              title="Remove all attachments"
            >
              <X className="w-4 h-4" />
            </Button>
          )}
        </>
      )}
    </div>
  );
}
