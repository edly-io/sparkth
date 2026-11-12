import { render } from "@testing-library/react";
import { beforeEach, describe, it, expect, vi } from "vitest";

import { ATTACHMENT_SOURCES } from "@/plugins/compose/lib";
import type { SelectedDriveFile } from "@/plugins/googledrive/src/components/ui/DriveFilePicker";
import GoogleDriveIcon from "@/plugins/googledrive/src/components/ui/GoogleDriveIcon";
import "@/plugins/googledrive/src/slots/attachments";

interface DrivePickerProps {
  initialSelectedFiles?: SelectedDriveFile[];
  onFileSelected: (files: SelectedDriveFile[]) => void;
  onClose: () => void;
}

// The props Google Drive's picker hands DriveFilePicker, captured on render and cleared before
// each test, so a test only sees its own render.
let pickerProps: DrivePickerProps | undefined;

vi.mock("@/plugins/googledrive/src/components/ui/DriveFilePicker", () => ({
  default: (props: DrivePickerProps) => {
    pickerProps = props;
    return null;
  },
}));

beforeEach(() => {
  pickerProps = undefined;
});

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
  expect(pickerProps).toBeDefined();
  return { onSelect, onClose, drivePicker: pickerProps! };
}

describe("Google Drive's attachment source", () => {
  it("offers Compose one source, picking from Google Drive with its icon", () => {
    const sources = ATTACHMENT_SOURCES.get("google-drive");

    expect(sources).toHaveLength(1);
    expect(sources![0].label).toBe("Pick from Google Drive");
    expect(sources![0].icon).toBe(GoogleDriveIcon);
  });

  it("passes the documents already attached back to the Drive picker as its selection", async () => {
    const { drivePicker } = await renderPicker();

    expect(drivePicker.initialSelectedFiles).toEqual([
      { document_id: 7, name: "notes.pdf", size: 1024 },
    ]);
  });

  it("hands the files picked in Drive to Compose as attached documents", async () => {
    const { onSelect, drivePicker } = await renderPicker();

    drivePicker.onFileSelected([
      { document_id: 8, name: "slides.pdf", mime_type: "application/pdf", size: 2048 },
    ]);

    expect(onSelect).toHaveBeenCalledWith([{ documentId: 8, name: "slides.pdf", size: 2048 }]);
  });

  it("closes when the Drive picker closes", async () => {
    const { onClose, drivePicker } = await renderPicker();

    drivePicker.onClose();

    expect(onClose).toHaveBeenCalledOnce();
  });
});
