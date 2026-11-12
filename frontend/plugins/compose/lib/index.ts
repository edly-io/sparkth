/**
 * Compose's public surface: the only part of Compose another plugin may import.
 *
 * It offers the attachment slot, through which a plugin adds a place Compose's attach menu can
 * pick documents from.
 */
export {
  ATTACHMENT_SOURCES,
  type AttachedDocument,
  type AttachmentPickerProps,
  type AttachmentSource,
} from "@/plugins/compose/src/slots/attachments";
