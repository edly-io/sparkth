"use client";

import { FileText, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { isUnsentUpload, TextAttachment } from "@/plugins/compose/src/types";
import { Button } from "@/lib/components/ui/Button";
import { Popover, PopoverTrigger, PopoverContent } from "@/lib/components/ui/Popover";
import { Spinner } from "@/lib/components/ui/Spinner";
import { truncate, DOCUMENT_DISPLAY_NAME_MAX_CHARS } from "@/plugins/compose/src/displayName";
import { ATTACHMENT_SOURCES } from "@/plugins/compose/src/slots/attachments";
import { slotItems } from "@/lib/slots";

interface AttachedFilesInfoProps {
  attachments: TextAttachment[];
  onRemoveFile: (attachment: TextAttachment) => void;
}

/**
 * The icon a listed file starts with: its attachment source's icon for a document, the file icon
 * for an upload from the computer or a document whose source isn't known.
 */
function fileIcon(file: TextAttachment) {
  const sources = slotItems(ATTACHMENT_SOURCES).map(([, source]) => source);
  return sources.find((source) => source.id === file.source)?.icon ?? FileText;
}

/**
 * The line above the message box counting the attached files. Opening it lists every file's name,
 * after an icon showing where it came from, each with a button that removes it, except a file
 * already sent, whose text the conversation keeps. While files upload, the line says which of the
 * files waiting to be sent is uploading, and a spinner takes the uploading file's icon's place.
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
            {attachments.map((file) => {
              const Icon = fileIcon(file);
              return (
                <li
                  key={file.documentId ?? file.uploadId}
                  className="flex items-center justify-between gap-2 text-sm"
                >
                  <span className="flex items-center gap-2 min-w-0">
                    {file.isUploading ? uploadingIndicator : <Icon className="w-4 h-4 shrink-0" />}
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
              );
            })}
          </ul>
        </PopoverContent>
      </Popover>
    </div>
  );
}
