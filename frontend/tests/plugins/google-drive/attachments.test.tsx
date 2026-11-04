import { render } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

import { ATTACHMENT_SOURCES } from "@/lib/attachments/slots";
import type { SelectedDriveFile } from "@/components/drive/DriveFilePicker";
import "@/plugins/google-drive/attachments";

// The props Google Drive's picker hands DriveFilePicker, captured on render.
let pickerProps: {
  initialSelectedFiles?: SelectedDriveFile[];
  onFileSelected: (files: SelectedDriveFile[]) => void;
  onClose: () => void;
};

vi.mock("@/components/drive/DriveFilePicker", () => ({
  default: (props: typeof pickerProps) => {
    pickerProps = props;
    return null;
  },
}));

async function renderPicker() {
  const source = ATTACHMENT_SOURCES.get("google-drive")?.[0];
  const { default: Picker } = await source!.loadPicker();
  const onSelect = vi.fn();
  const onClose = vi.fn();
  render(
    <Picker
      selected={[{ documentId: 7, name: "notes.pdf", size: 1024 }]}
      onSelect={onSelect}
      onClose={onClose}
    />,
  );
  return { onSelect, onClose };
}

describe("Google Drive's attachment source", () => {
  it("offers Compose one source, picking from Google Drive", () => {
    const sources = ATTACHMENT_SOURCES.get("google-drive");

    expect(sources).toHaveLength(1);
    expect(sources![0].label).toBe("Pick from Google Drive");
  });

  it("passes the documents already attached back to the Drive picker as its selection", async () => {
    await renderPicker();

    expect(pickerProps.initialSelectedFiles).toEqual([
      { document_id: 7, name: "notes.pdf", size: 1024 },
    ]);
  });

  it("hands the files picked in Drive to Compose as attached documents", async () => {
    const { onSelect } = await renderPicker();

    pickerProps.onFileSelected([
      { document_id: 8, name: "slides.pdf", mime_type: "application/pdf", size: 2048 },
    ]);

    expect(onSelect).toHaveBeenCalledWith([
      { documentId: 8, name: "slides.pdf", size: 2048 },
    ]);
  });

  it("closes when the Drive picker closes", async () => {
    const { onClose } = await renderPicker();

    pickerProps.onClose();

    expect(onClose).toHaveBeenCalledOnce();
  });
});
