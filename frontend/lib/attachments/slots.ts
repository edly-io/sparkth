/**
 * The slot through which a plugin offers Compose a place to attach documents from.
 *
 * A plugin sets an `AttachmentSource` under its name. Compose's attach menu lists each source
 * while its plugin is enabled and opens the source's picker when the user chooses it, so Compose
 * knows nothing about any source itself.
 */

import type { ComponentType } from "react";

import type { Slot } from "@/lib/slots";

/** A document a source picked, which Compose attaches to the message. */
export interface AttachedDocument {
  documentId: number;
  name: string;
  size?: number;
}

/** What Compose passes to a source's picker. */
export interface AttachmentPickerProps {
  /** The documents already attached, so the picker opens with them selected. */
  selected: AttachedDocument[];
  /** Replaces the attached documents with the ones the user picked. */
  onSelect: (documents: AttachedDocument[]) => void;
  onClose: () => void;
}

/** A place Compose's attach menu can pick documents from. */
export interface AttachmentSource {
  /** The attach menu's entry for the source. */
  label: string;
  icon: ComponentType<{ className?: string }>;
  /** Loads the source's picker, only when the user chooses the source. */
  loadPicker: () => Promise<{ default: ComponentType<AttachmentPickerProps> }>;
}

/** The sources each plugin offers Compose's attach menu. */
export const ATTACHMENT_SOURCES: Slot<AttachmentSource> = new Map();
