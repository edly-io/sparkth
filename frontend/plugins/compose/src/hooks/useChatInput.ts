"use client";

import { Dispatch, SetStateAction, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { isUnsentUpload, TextAttachment } from "@/plugins/compose/src/types";
import {
  attachDocument,
  detachDocument,
  removeConversationUploadedFile,
} from "@/plugins/compose/src/client";
import { uploadFile, UploadResponse } from "@/plugins/compose/src/upload";
import type { AttachedDocument, AttachmentSource } from "@/plugins/compose/src/slots/attachments";

/** How many megabytes of computer files one conversation can carry; documents don't count. */
const MAX_COMBINED_UPLOAD_MB = 3;
const MAX_COMBINED_UPLOAD_BYTES = MAX_COMBINED_UPLOAD_MB * 1024 * 1024;

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
  const t = useTranslations("compose");
  // Each upload in progress, by upload ID, so removing its file can cancel it.
  const uploadsInProgress = useRef(new Map<string, AbortController>());

  const uploadComputerFile = async (file: File) => {
    // Listed straight away, so the user sees the file while it uploads.
    const uploadId = crypto.randomUUID();
    setAttachments((prev) => [
      ...prev,
      { name: file.name, size: file.size, uploadId, isUploading: true },
    ]);

    const cancelUpload = new AbortController();
    uploadsInProgress.current.set(uploadId, cancelUpload);
    try {
      const formData = new FormData();
      formData.append("file", file);

      const data: UploadResponse = await uploadFile(
        formData,
        token ?? undefined,
        cancelUpload.signal,
      );

      setAttachments((prev) =>
        prev.map((a) =>
          a.uploadId === uploadId ? { ...a, text: data.text, isUploading: false } : a,
        ),
      );
    } catch (error) {
      // A cancelled upload's file was already removed by the user.
      if (cancelUpload.signal.aborted) return;
      setAttachments((prev) => prev.filter((a) => a.uploadId !== uploadId));
      const reason = error instanceof Error ? error.message : String(error);
      setUploadError(t("uploadFailed", { name: file.name, reason }));
    } finally {
      uploadsInProgress.current.delete(uploadId);
    }
  };

  const handleUploadFromComputer = async (files: File[]) => {
    setUploadError(null);

    // A file with the name of a listed upload, sent or not, is taken as the same file.
    const listedUploads = attachments.filter((a) => a.documentId === undefined);
    const isListed = (file: File) => listedUploads.some((a) => a.name === file.name);
    const duplicateFiles = files.filter(isListed);
    const newFiles = files.filter((file) => !isListed(file));

    if (duplicateFiles.length > 0) {
      setUploadError(t("uploadSkippedDuplicates", { count: duplicateFiles.length }));
    }

    const listedBytes = listedUploads.reduce((total, a) => total + a.size, 0);
    const newBytes = newFiles.reduce((total, file) => total + file.size, 0);
    if (listedBytes + newBytes > MAX_COMBINED_UPLOAD_BYTES) {
      setUploadError(t("uploadLimitExceeded", { limitMb: MAX_COMBINED_UPLOAD_MB }));
      return;
    }

    await Promise.all(newFiles.map(uploadComputerFile));
  };

  const handleDocumentsSelected = (documents: AttachedDocument[]) => {
    setPickingFrom(null);
    setUploadError(null);

    // Snapshot the previous document attachments before enqueueing the state
    // update so both diff computations read a consistent pre-update view.
    const prevDocumentAttachments = attachments.filter((a) => a.documentId !== undefined);

    // A newly picked document comes from the open picker's source; one picked again keeps the
    // source it had.
    const newDocumentAttachments = documents.map((document) => {
      const source =
        prevDocumentAttachments.find((a) => a.documentId === document.documentId)?.source ??
        pickingFrom?.id;
      return {
        name: document.name,
        size: document.size ?? 0,
        documentId: document.documentId,
        source,
      };
    });
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
          setUploadError(t("attachFailed", { name: document.name }));
          setAttachments((prev) => prev.filter((a) => a.documentId !== document.documentId));
        });
      }

      const newIds = new Set(documents.map((d) => d.documentId));
      const removedAttachments = prevDocumentAttachments.filter((a) => !newIds.has(a.documentId!));
      for (const att of removedAttachments) {
        detachDocument(token, conversationId, att.documentId!).catch((err) => {
          console.warn("Failed to detach document:", err);
          setUploadError(t("detachFailed", { name: att.name }));
          setAttachments((prev) => [...prev, att]);
        });
      }
    }
  };

  // Removing a file that is still uploading also cancels its upload, and removing a sent one also
  // takes it out of the conversation on the server.
  const handleRemoveAttachment = (removed: TextAttachment) => {
    const { documentId, uploadId } = removed;
    if (documentId === undefined) {
      if (uploadId !== undefined) uploadsInProgress.current.get(uploadId)?.abort();
      setAttachments((prev) => prev.filter((a) => a.uploadId !== uploadId));
      // The server keeps a sent upload for the conversation, so it has to forget it too.
      if (removed.isSent && conversationId) {
        removeConversationUploadedFile(token, conversationId, removed.name).catch((err) => {
          console.warn("Failed to remove uploaded file:", err);
          setUploadError(t("detachFailed", { name: removed.name }));
          setAttachments((prev) => [...prev, removed]);
        });
      }
      return;
    }

    setAttachments((prev) => prev.filter((a) => a.documentId !== documentId));
    if (conversationId) {
      detachDocument(token, conversationId, documentId).catch((err) => {
        console.warn("Failed to detach document:", err);
        setUploadError(t("detachFailed", { name: removed.name }));
        setAttachments((prev) => [...prev, removed]);
      });
    }
  };

  // A message must be typed, with or without files, and every upload must have finished.
  const canSend = message.trim() !== "" && !attachments.some((a) => a.isUploading);

  const handleSend = async () => {
    if (!canSend) return;

    const unsentUploads = attachments.filter(isUnsentUpload);

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
    // Every file stays listed: documents remain attached, and the server keeps a sent upload for the
    // conversation.
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
    handleUploadFromComputer,
    handleDocumentsSelected,
    handleRemoveAttachment,
    canSend,
    handleSend,
  };
}
