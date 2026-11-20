"use client";

import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { isUnsentUpload, TextAttachment } from "@/plugins/compose/src/types";
import { Button } from "@/lib/components/ui/Button";
import { Popover, PopoverTrigger, PopoverContent } from "@/lib/components/ui/Popover";
import { Spinner } from "@/lib/components/ui/Spinner";
import { truncate, DOCUMENT_DISPLAY_NAME_MAX_CHARS } from "@/plugins/compose/src/displayName";

interface AttachedFilesInfoProps {
  attachments: TextAttachment[];
  onRemoveFile: (attachment: TextAttachment) => void;
}

/**
 * The line above the message box counting the attached files. Opening it lists every file's name,
 * each with a button that removes it, except a file already sent, whose text the conversation keeps.
 * While files upload, the line says which of the files waiting to be sent is uploading, and a
 * spinner starts the uploading file's row.
 */
export function AttachedFilesInfo({ attachments, onRemoveFile }: AttachedFilesInfoProps) {
  const t = useTranslations("compose");

  if (attachments.length === 0) return null;

  // The computer files waiting to go with the next message, which the upload progress counts.
  const unsentUploads = attachments.filter(isUnsentUpload);

  const uploadingIndicator = (
    <span role="status" aria-label={t("uploadingFile")} className="inline-flex shrink-0">
      <Spinner size="sm" />
    </span>
  );

  return (
    <div className="text-sm text-muted-foreground">
      <Popover>
        <PopoverTrigger asChild>
          <span className="inline-flex items-center gap-2 cursor-pointer">
            <span className="underline">
              {t("attachedFileCount", { count: attachments.length })}
            </span>
            {unsentUploads.some((file) => file.isUploading) && (
              <span role="status">
                {t("uploadingFileProgress", {
                  current: unsentUploads.filter((file) => !file.isUploading).length + 1,
                  total: unsentUploads.length,
                })}
              </span>
            )}
          </span>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-72 p-2">
          <ul className="space-y-1">
            {attachments.map((file) => (
              <li
                key={file.documentId ?? file.uploadId}
                className="flex items-center justify-between gap-2 text-sm"
              >
                <span className="flex items-center gap-2 min-w-0">
                  {file.isUploading && uploadingIndicator}
                  <span className="truncate">
                    {truncate(file.name, DOCUMENT_DISPLAY_NAME_MAX_CHARS)}
                  </span>
                </span>
                {!file.isSent && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="p-0 h-auto text-muted-foreground hover:text-foreground flex-shrink-0"
                    title={t("removeAttachedFile")}
                    onClick={() => onRemoveFile(file)}
                  >
                    <X className="w-4 h-4" />
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </PopoverContent>
      </Popover>
    </div>
  );
}
