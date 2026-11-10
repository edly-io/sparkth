"use client";

import type { AttachmentPickerProps } from "@/lib/attachments/slots";
import DriveFilePicker from "@/components/drive/DriveFilePicker";

/** Compose's picker for Google Drive: the Drive file picker, speaking in attached documents. */
export default function AttachmentPicker({ selected, onSelect, onClose }: AttachmentPickerProps) {
  return (
    <DriveFilePicker
      onClose={onClose}
      initialSelectedFiles={selected.map((document) => ({
        document_id: document.documentId,
        name: document.name,
        size: document.size,
      }))}
      // A file's mime_type is not passed on: Compose attaches a document by its id and name only.
      onFileSelected={(files) =>
        onSelect(
          files.map((file) => ({
            documentId: file.document_id,
            name: file.name,
            size: file.size,
          })),
        )
      }
    />
  );
}
