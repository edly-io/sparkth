"use client";

import { Dispatch, SetStateAction, useState } from "react";
import { TextAttachment } from "@/plugins/chat/types";
import { attachDocument, detachDocument } from "@/lib/chat";
import { uploadFile, UploadResponse } from "@/lib/file-upload";
import { SelectedDriveFile } from "@/components/drive/DriveFilePicker";

const MAX_FILE_SIZE = 30 * 1024 * 1024; // 30MB

interface UseChatInputProps {
  token: string | null;
  conversationId: string | null;
  attachments: TextAttachment[];
  setAttachments: Dispatch<SetStateAction<TextAttachment[]>>;
  onSend: (payload: {
    message: string;
    attachments: TextAttachment[];
    documentIds?: number[];
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

      setAttachments((prev) => [
        ...prev,
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

    // Snapshot the previous drive attachments before enqueueing the state
    // update so both diff computations read a consistent pre-update view.
    const prevDocumentAttachments = attachments.filter((a) => a.documentId !== undefined);

    const newDriveAttachments = driveFiles.map((file) => ({
      name: file.name,
      size: file.size ?? 0,
      text: `[File: ${file.name}]`,
      driveFileDbId: file.id,
      documentId: file.document_id,
    }));
    setAttachments((prev) => {
      const nonDrive = prev.filter((a) => a.documentId === undefined);
      return [...nonDrive, ...newDriveAttachments];
    });

    if (conversationId) {
      const existingIds = new Set(prevDocumentAttachments.map((a) => a.documentId));
      const addedFiles = driveFiles.filter((f) => !existingIds.has(f.document_id));
      for (const file of addedFiles) {
        attachDocument(token, conversationId, file.document_id).catch((err) => {
          console.warn("Failed to persist drive file attachment:", err);
          setUploadError(`Failed to attach "${file.name}". Please try again.`);
          setAttachments((prev) => prev.filter((a) => a.documentId !== file.document_id));
        });
      }

      const newIds = new Set(driveFiles.map((f) => f.document_id));
      const removedAttachments = prevDocumentAttachments.filter((a) => !newIds.has(a.documentId!));
      for (const att of removedAttachments) {
        detachDocument(token, conversationId, att.documentId!).catch((err) => {
          console.warn("Failed to detach drive file:", err);
          setUploadError(`Failed to detach "${att.name}". Please try again.`);
          setAttachments((prev) => [...prev, att]);
        });
      }
    }
  };

  const handleRemoveAttachment = (documentId?: number) => {
    if (documentId !== undefined) {
      const removed = attachments.find((a) => a.documentId === documentId);
      setAttachments((prev) => prev.filter((a) => a.documentId !== documentId));
      if (conversationId && removed) {
        detachDocument(token, conversationId, documentId).catch((err) => {
          console.warn("Failed to detach drive file:", err);
          setUploadError(`Failed to detach "${removed.name}". Please try again.`);
          setAttachments((prev) => [...prev, removed]);
        });
      }
    } else {
      const driveAtts = attachments.filter((a) => a.documentId !== undefined);
      setAttachments([]);
      if (conversationId) {
        for (const att of driveAtts) {
          detachDocument(token, conversationId, att.documentId!).catch((err) => {
            console.warn("Failed to detach drive file:", err);
            setUploadError("Some files could not be detached. Please try again.");
            setAttachments((prev) => [...prev, att]);
          });
        }
      }
    }
  };

  const handleSend = () => {
    const sendableAttachments = attachments.filter((a) => a.documentId === undefined);
    if (!message.trim() && sendableAttachments.length === 0) return;

    const documentAttachments = attachments.filter((a) => a.documentId !== undefined);
    const documentIds = documentAttachments.map((a) => a.documentId!);

    onSend({
      message: message.trim(),
      attachments: sendableAttachments,
      // Always send document IDs so the backend can attach them before processing
      // (critical for new conversations where they haven't been persisted yet)
      ...(documentIds.length > 0 && { documentIds }),
    });

    setMessage("");
    // Keep document attachments in state — they remain attached to the conversation
    setAttachments(documentAttachments);
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
