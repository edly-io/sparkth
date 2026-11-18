"use client";

import { Dispatch, SetStateAction, useState } from "react";
import { TextAttachment } from "@/plugins/compose/src/types";
import { attachDocument, detachDocument } from "@/plugins/compose/src/client";
import { uploadFile, UploadResponse } from "@/plugins/compose/src/upload";
import type { AttachedDocument, AttachmentSource } from "@/plugins/compose/src/slots/attachments";

const MAX_FILE_SIZE = 30 * 1024 * 1024; // 30MB

interface UseChatInputProps {
  message: string;
  setMessage: Dispatch<SetStateAction<string>>;
  token: string | null;
  conversationId: string | null;
  attachments: TextAttachment[];
  setAttachments: Dispatch<SetStateAction<TextAttachment[]>>;
  onSend: (payload: {
    message: string;
    attachments: TextAttachment[];
    documentIds?: number[];
  }) => Promise<boolean>;
}

export function useChatInput({
  message,
  setMessage,
  token,
  conversationId,
  attachments,
  setAttachments,
  onSend,
}: UseChatInputProps) {
  const [showUploadMenu, setShowUploadMenu] = useState(false);
  const [pickingFrom, setPickingFrom] = useState<AttachmentSource | null>(null);
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
          uploadId: crypto.randomUUID(),
        },
      ]);

      setShowUploadMenu(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to upload file";
      setUploadError(message);
    }
  };

  const handleDocumentsSelected = (documents: AttachedDocument[]) => {
    setPickingFrom(null);
    setUploadError(null);

    // Snapshot the previous document attachments before enqueueing the state
    // update so both diff computations read a consistent pre-update view.
    const prevDocumentAttachments = attachments.filter((a) => a.documentId !== undefined);

    const newDocumentAttachments = documents.map((document) => ({
      name: document.name,
      size: document.size ?? 0,
      text: `[File: ${document.name}]`,
      documentId: document.documentId,
    }));
    setAttachments((prev) => {
      const nonDocument = prev.filter((a) => a.documentId === undefined);
      return [...nonDocument, ...newDocumentAttachments];
    });

    if (conversationId) {
      const existingIds = new Set(prevDocumentAttachments.map((a) => a.documentId));
      const addedDocuments = documents.filter((d) => !existingIds.has(d.documentId));
      for (const document of addedDocuments) {
        attachDocument(token, conversationId, document.documentId).catch((err) => {
          console.warn("Failed to persist document attachment:", err);
          setUploadError(`Failed to attach "${document.name}". Please try again.`);
          setAttachments((prev) => prev.filter((a) => a.documentId !== document.documentId));
        });
      }

      const newIds = new Set(documents.map((d) => d.documentId));
      const removedAttachments = prevDocumentAttachments.filter((a) => !newIds.has(a.documentId!));
      for (const att of removedAttachments) {
        detachDocument(token, conversationId, att.documentId!).catch((err) => {
          console.warn("Failed to detach document:", err);
          setUploadError(`Failed to detach "${att.name}". Please try again.`);
          setAttachments((prev) => [...prev, att]);
        });
      }
    }
  };

  const handleRemoveAttachment = (removed: TextAttachment) => {
    const { documentId, uploadId } = removed;
    if (documentId === undefined) {
      setAttachments((prev) => prev.filter((a) => a.uploadId !== uploadId));
      return;
    }

    setAttachments((prev) => prev.filter((a) => a.documentId !== documentId));
    if (conversationId) {
      detachDocument(token, conversationId, documentId).catch((err) => {
        console.warn("Failed to detach document:", err);
        setUploadError(`Failed to detach "${removed.name}". Please try again.`);
        setAttachments((prev) => [...prev, removed]);
      });
    }
  };

  const handleSend = async () => {
    const unsentUploads = attachments.filter((a) => a.documentId === undefined && !a.isSent);
    if (!message.trim() && unsentUploads.length === 0) return;

    const documentIds = attachments.flatMap((a) =>
      a.documentId === undefined ? [] : [a.documentId],
    );

    // Cleared only once accepted, so a refused send keeps what the author typed.
    const accepted = await onSend({
      message: message.trim(),
      attachments: unsentUploads,
      // Always send document IDs so the backend can attach them before processing
      // (critical for new conversations where they haven't been persisted yet)
      ...(documentIds.length > 0 && { documentIds }),
    });
    if (!accepted) return;

    setMessage("");
    // Every file stays listed: documents remain attached, and a sent upload's text is now part of
    // the conversation.
    const sentUploadIds = new Set(unsentUploads.map((a) => a.uploadId));
    setAttachments((prev) =>
      prev.map((a) =>
        a.uploadId !== undefined && sentUploadIds.has(a.uploadId) ? { ...a, isSent: true } : a,
      ),
    );
  };

  return {
    showUploadMenu,
    setShowUploadMenu,
    pickingFrom,
    setPickingFrom,
    uploadError,
    setUploadError,
    handleUploadAsText,
    handleDocumentsSelected,
    handleRemoveAttachment,
    handleSend,
  };
}
