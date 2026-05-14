"use client";

import { useState } from "react";
import { TextAttachment } from "@/plugins/chat/types";
import { uploadFile, UploadResponse } from "@/lib/file_upload";
import { SelectedDriveFile } from "@/components/drive/DriveFilePicker";

const MAX_FILE_SIZE = 30 * 1024 * 1024; // 30MB

interface UseChatInputProps {
  token: string | null;
  conversationId: string | null;
  attachments: TextAttachment[];
  setAttachments: (attachments: TextAttachment[]) => void;
  onSend: (payload: {
    message: string;
    attachments: TextAttachment[];
    driveFileIds?: number[];
  }) => void;
}

export function useChatInput({
  token,
  conversationId,
  attachments,
  setAttachments,
  onSend,
}: UseChatInputProps) {
  const [message, setMessage] = useState("");
  const [showUploadMenu, setShowUploadMenu] = useState(false);
  const [showDriveFilePicker, setShowDriveFilePicker] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

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

      setAttachments([
        ...attachments,
        {
          name: file.name,
          size: file.size,
          text: data.text,
        },
      ]);

      setShowUploadMenu(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to upload file";
      setUploadError(message);
    }
  };

  const handleDriveFileSelected = (driveFiles: SelectedDriveFile[]) => {
    setShowDriveFilePicker(false);
    setUploadError(null);
    const nonDriveAttachments = attachments.filter((a) => a.driveFileDbId === undefined);
    const newDriveAttachments = driveFiles.map((file) => ({
      name: file.name,
      size: file.size ?? 0,
      text: `[File: ${file.name}]`,
      driveFileDbId: file.id,
    }));
    setAttachments([...nonDriveAttachments, ...newDriveAttachments]);

    if (conversationId) {
      const existingIds = new Set(
        attachments.filter((a) => a.driveFileDbId).map((a) => a.driveFileDbId),
      );
      const addedFiles = driveFiles.filter((f) => !existingIds.has(f.id));
      for (const file of addedFiles) {
        fetch(`/api/v1/chat/conversations/${conversationId}/attachments`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify({ drive_file_id: file.id }),
        }).catch((err) => console.warn("Failed to persist drive file attachment:", err));
      }
    }
  };

  const handleRemoveAttachment = (driveFileDbId?: number) => {
    if (driveFileDbId !== undefined) {
      setAttachments(attachments.filter((a) => a.driveFileDbId !== driveFileDbId));
      if (conversationId) {
        fetch(`/api/v1/chat/conversations/${conversationId}/attachments/${driveFileDbId}`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        }).catch((err) => console.warn("Failed to detach drive file:", err));
      }
    } else {
      setAttachments([]);
    }
  };

  const handleSend = () => {
    const sendableAttachments = attachments.filter((a) => a.driveFileDbId === undefined);
    if (!message.trim() && sendableAttachments.length === 0) return;

    const driveFileAttachments = attachments.filter((a) => a.driveFileDbId !== undefined);
    const driveFileIds = driveFileAttachments.map((a) => a.driveFileDbId!);

    onSend({
      message: message.trim(),
      attachments: sendableAttachments,
      // Always send drive file IDs so the backend can attach them before processing
      // (critical for new conversations where they haven't been persisted yet)
      ...(driveFileIds.length > 0 && { driveFileIds }),
    });

    setMessage("");
    // Keep drive file attachments in state — they remain attached to the conversation
    setAttachments(driveFileAttachments);
  };

  return {
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
  };
}
