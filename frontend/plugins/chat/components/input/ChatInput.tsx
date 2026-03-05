"use client";

import { useState } from "react";
import { Paperclip, ArrowUp, Loader2, X } from "lucide-react";
import { UploadMenu } from "./UploadMenu";
import { TextAttachment } from "../../types";
import { uploadFile, UploadResponse } from "@/lib/file_upload";
import { Pill } from "../attachment/Pill";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth-context";
import { useIsPluginEnabled } from "@/lib/plugins/usePlugins";
import { downloadFile } from "@/lib/drive";
import DriveFilePicker, { SelectedDriveFile } from "@/components/drive/DriveFilePicker";

interface ChatInputProps {
  attachment: TextAttachment | null;
  setAttachment: (attachment: TextAttachment | null) => void;
  setPreviewAttachment: (attachment: TextAttachment | null) => void;
  setPreviewOpen: (open: boolean) => void;
  onSend: (payload: {
    message: string;
    attachment: TextAttachment | null;
  }) => void;
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
  const [isLoadingDriveFile, setIsLoadingDriveFile] = useState(false);
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

  const handleDriveFileSelected = async (driveFile: SelectedDriveFile) => {
    if (!token) return;

    setShowDriveFilePicker(false);
    setIsLoadingDriveFile(true);
    setUploadError(null);

    try {
      const blob = await downloadFile(driveFile.id, token);

      if (blob.size > MAX_FILE_SIZE) {
        setUploadError("File size exceeds 30MB limit");
        return;
      }

      const mediaType = blob.type || driveFile.mime_type || "application/octet-stream";
      const base64Data = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
          const result = reader.result as string;
          resolve(result.split(",")[1]);
        };
        reader.onerror = () => reject(new Error("Failed to read file"));
        reader.readAsDataURL(blob);
      });

      setAttachment({
        name: driveFile.name,
        size: blob.size,
        text: `[File: ${driveFile.name}]`,
        base64Data,
        mediaType,
      });
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Failed to download file from Google Drive";
      setUploadError(msg);
    } finally {
      setIsLoadingDriveFile(false);
    }
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

        {/* Loading indicator for Drive file download */}
        {isLoadingDriveFile && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-muted-foreground bg-surface-variant">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Downloading file from Google Drive...</span>
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
                if (!isLoadingDriveFile) handleSend();
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
                onClick={() => setShowUploadMenu((v) => !v)}
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
                disabled={isLoadingDriveFile || (!message.trim() && !attachment)}
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
