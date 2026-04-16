"use client";

import { useState } from "react";
import { Paperclip, ArrowUp, X } from "lucide-react";
import { UploadMenu } from "./UploadMenu";
import { TextAttachment } from "../../types";
import { uploadFile, UploadResponse } from "@/lib/file_upload";
import { Pill } from "../attachment/Pill";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth-context";
import { useIsPluginEnabled } from "@/lib/plugins/usePlugins";
import DriveFilePicker, { SelectedDriveFile } from "@/components/drive/DriveFilePicker";

interface ChatInputProps {
  attachment: TextAttachment | null;
  setAttachment: (attachment: TextAttachment | null) => void;
  setPreviewAttachment: (attachment: TextAttachment | null) => void;
  setPreviewOpen: (open: boolean) => void;
  onSend: (payload: { message: string; attachment: TextAttachment | null }) => void;
}

export function ChatInput({
  attachment,
  setAttachment,
  setPreviewAttachment,
  setPreviewOpen,
  onSend,
}: ChatInputProps) {
  const { token } = useAuth();
  const [message, setMessage] = useState("");
  const [showUploadMenu, setShowUploadMenu] = useState(false);
  const [showDriveFilePicker, setShowDriveFilePicker] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const { isEnabled: isDriveEnabled } = useIsPluginEnabled(token, "google-drive");

  const MAX_FILE_SIZE = 30 * 1024 * 1024; // 30MB

  const handleUploadAsText = async (file: File) => {
    setUploadError(null);

    if (file.size > MAX_FILE_SIZE) {
      setUploadError("File size exceeds 30MB limit");
      return;
    }

    try {
      const formData = new FormData();
      formData.append("file", file);

      const data: UploadResponse = await uploadFile(formData, token ?? undefined);

      setAttachment({
        name: file.name,
        size: file.size,
        text: data.text,
      });

      setShowUploadMenu(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to upload file";
      setUploadError(message);
    }
  };

  const handleDriveFileSelected = (driveFile: SelectedDriveFile) => {
    setShowDriveFilePicker(false);
    setUploadError(null);
    setAttachment({
      name: driveFile.name,
      size: driveFile.size ?? 0,
      text: `[File: ${driveFile.name}]`,
      driveFileDbId: driveFile.id,
    });
  };

  const handleSend = () => {
    if (!message.trim() && !attachment) return;

    onSend({
      message: message.trim(),
      attachment,
    });

    setMessage("");
    setAttachment(null);
  };

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
        <Pill
          attachment={attachment}
          onOpen={() => {
            setPreviewAttachment(attachment);
            setPreviewOpen(true);
          }}
          onRemove={() => setAttachment(null)}
        />

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
              <Button variant="ghost" size="icon" onClick={() => setShowUploadMenu((v) => !v)}>
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
                disabled={!message.trim() && !attachment}
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
        />
      )}
    </div>
  );
}
