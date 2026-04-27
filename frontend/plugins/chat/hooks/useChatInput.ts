"use client";

import { useState } from "react";
import { TextAttachment } from "@/plugins/chat/types";
import { uploadFile, UploadResponse } from "@/lib/file_upload";
import { SelectedDriveFile } from "@/components/drive/DriveFilePicker";

const MAX_FILE_SIZE = 30 * 1024 * 1024; // 30MB

interface UseChatInputProps {
  token: string | null;
  attachments: TextAttachment[];
  setAttachments: (attachments: TextAttachment[]) => void;
  onSend: (payload: { message: string; attachments: TextAttachment[] }) => void;
}

export function useChatInput({ token, attachments, setAttachments, onSend }: UseChatInputProps) {
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
    const newAttachments = driveFiles.map((file) => ({
      name: file.name,
      size: file.size ?? 0,
      text: `[File: ${file.name}]`,
      driveFileDbId: file.id,
    }));
    setAttachments([...attachments, ...newAttachments]);
  };

  const handleRemoveAttachment = () => {
    setAttachments([]);
  };

  const handleSend = () => {
    if (!message.trim() && attachments.length === 0) return;

    onSend({
      message: message.trim(),
      attachments,
    });

    setMessage("");
    // Drive file attachments persist across the session until explicitly removed
    const hasDriveFiles = attachments.some((a) => a.driveFileDbId);
    if (!hasDriveFiles) {
      setAttachments([]);
    }
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
