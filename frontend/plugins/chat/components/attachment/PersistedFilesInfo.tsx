"use client";

import { X } from "lucide-react";
import { TextAttachment } from "../../types";
import { Button } from "@/components/ui/Button";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/Popover";
import { truncate, RAG_DISPLAY_NAME_MAX_CHARS } from "@/lib/utils";

interface PersistedFilesInfoProps {
  attachments: TextAttachment[];
  onDetachFile: (driveFileDbId: number) => void;
}

export function PersistedFilesInfo({ attachments, onDetachFile }: PersistedFilesInfoProps) {
  const driveAttachments = attachments.filter((a) => a.driveFileDbId !== undefined);

  if (driveAttachments.length === 0) return null;

  const count = driveAttachments.length;
  const label = count === 1 ? "1 file" : `${count} files`;

  return (
    <div className="text-sm text-muted-foreground">
      <Popover>
        <PopoverTrigger asChild>
          <span className="underline cursor-pointer">{label}</span>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-72 p-2">
          <ul className="space-y-1">
            {driveAttachments.map((file) => (
              <li
                key={file.driveFileDbId}
                className="flex items-center justify-between gap-2 text-sm"
              >
                <span className="truncate">{truncate(file.name, RAG_DISPLAY_NAME_MAX_CHARS)}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  className="p-0 h-auto text-muted-foreground hover:text-foreground flex-shrink-0"
                  title="Remove file"
                  onClick={() => onDetachFile(file.driveFileDbId!)}
                >
                  <X className="w-4 h-4" />
                </Button>
              </li>
            ))}
          </ul>
        </PopoverContent>
      </Popover>
      {" will be read for relevant context"}
    </div>
  );
}
