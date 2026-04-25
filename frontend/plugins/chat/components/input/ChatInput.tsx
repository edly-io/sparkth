"use client";

import { Paperclip, ArrowUp, X } from "lucide-react";
import { UploadMenu } from "./UploadMenu";
import { TextAttachment } from "../../types";
import { Pill } from "../attachment/Pill";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth-context";
import { useIsPluginEnabled } from "@/lib/plugins/usePlugins";
import DriveFilePicker from "@/components/drive/DriveFilePicker";
import { useChatInput } from "../../hooks/useChatInput";

interface ChatInputProps {
  attachments: TextAttachment[];
  setAttachments: (attachments: TextAttachment[]) => void;
  setPreviewAttachment: (attachment: TextAttachment | null) => void;
  setPreviewOpen: (open: boolean) => void;
  onSend: (payload: { message: string; attachments: TextAttachment[] }) => void;
}

export function ChatInput({
  attachments,
  setAttachments,
  setPreviewAttachment,
  setPreviewOpen,
  onSend,
}: ChatInputProps) {
  const { token } = useAuth();

  const {
    message,
    setMessage,
    showUploadMenu,
    setShowUploadMenu,
    showDriveFilePicker,
    setShowDriveFilePicker,
    uploadError,
    setUploadError,
    handleUploadAsText,
    handleDriveFileSelected,
    handleRemoveAttachment,
    handleSend,
  } = useChatInput({ token, attachments, setAttachments, onSend });

  const { isEnabled: isDriveEnabled } = useIsPluginEnabled(token, "google-drive");

  return (
    <div className="border-t border-border p-4">
      <div className="mx-auto space-y-2">
        {/* Upload error */}
        {uploadError && (
          <div className="flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/30">
            <span className="truncate">{uploadError}</span>
            <button onClick={() => setUploadError(null)} className="shrink-0">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Attachment pill */}
        {attachments.length > 0 && (
          <Pill
            attachments={attachments}
            onPreview={(attachment) => {
              setPreviewAttachment(attachment);
              setPreviewOpen(true);
            }}
            onRemove={handleRemoveAttachment}
          />
        )}

        {/* Input box */}
        <div className="relative bg-input border border-border rounded-2xl p-3">
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Describe the course you want to create..."
            rows={1}
            className="w-full bg-transparent resize-none focus:outline-none"
          />

          <div className="flex justify-between mt-2">
            <div className="relative">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowUploadMenu(!showUploadMenu)}
              >
                <Paperclip className="w-5 h-5" />
              </Button>

              {showUploadMenu && (
                <UploadMenu
                  onClose={() => setShowUploadMenu(false)}
                  onUploadText={handleUploadAsText}
                  isDriveEnabled={isDriveEnabled}
                  onPickFromDrive={() => setShowDriveFilePicker(true)}
                />
              )}
            </div>

            <div className="flex gap-1">
              {/* TODO: Voice input - disabled for now
              <Button variant="ghost" size="icon">
                <Mic className="w-5 h-5" />
              </Button>
              */}

              <Button
                variant="primary"
                size="icon"
                onClick={handleSend}
                disabled={!message.trim() && attachments.length === 0}
                className="rounded-full bg-foreground text-background"
              >
                <ArrowUp className="w-5 h-5" />
              </Button>
            </div>
          </div>
        </div>
      </div>

      {showDriveFilePicker && (
        <DriveFilePicker
          onClose={() => setShowDriveFilePicker(false)}
          onFileSelected={handleDriveFileSelected}
          selectedFileIds={attachments.map((a) => a.driveFileDbId).filter((id) => id !== undefined)}
        />
      )}
    </div>
  );
}
