"use client";

import { useState } from "react";
import { TextAttachment } from "@/plugins/chat/types";
import { uploadFile, UploadResponse } from "@/lib/file_upload";
import { SelectedDriveFile } from "@/components/drive/DriveFilePicker";

const MAX_FILE_SIZE = 30 * 1024 * 1024; // 30MB

interface UseChatInputProps {
  token: string | null;
  attachment: TextAttachment | null;
  setAttachment: (a: TextAttachment | null) => void;
  onSend: (payload: { message: string; attachment: TextAttachment | null }) => void;
}

export function useChatInput({ token, attachment, setAttachment, onSend }: UseChatInputProps) {
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
    // Drive file attachments persist across the session until explicitly removed
    if (!attachment?.driveFileDbId) {
      setAttachment(null);
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
    handleSend,
  };
}
