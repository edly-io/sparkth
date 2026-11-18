import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { AttachedFilesInfo } from "@/plugins/compose/src/components/ui/attachment/AttachedFilesInfo";
import { TextAttachment } from "@/plugins/compose/src/types";
import { DOCUMENT_DISPLAY_NAME_MAX_CHARS } from "@/plugins/compose/src/displayName";
import composeEn from "@/plugins/compose/src/i18n/en.json";
import { renderWithIntl } from "@/lib/testing/intl";

describe("AttachedFilesInfo", () => {
  const onRemoveFile = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  const makeDocument = (id: number, name: string): TextAttachment => ({
    name,
    text: "content",
    size: 1024,
    documentId: id,
  });

  const makeComputerFile = (uploadId: string, name: string): TextAttachment => ({
    name,
    text: "content",
    size: 512,
    uploadId,
  });

  function renderInfo(attachments: TextAttachment[]) {
    return renderWithIntl(
      <AttachedFilesInfo attachments={attachments} onRemoveFile={onRemoveFile} />,
      composeEn,
    );
  }

  it("renders nothing when no file is attached", () => {
    const { container } = renderInfo([]);

    expect(container.firstChild).toBeNull();
  });

  it("counts a single attached file", () => {
    renderInfo([makeDocument(1, "test.pdf")]);

    expect(screen.getByText("1 file attached")).toBeInTheDocument();
  });

  it("counts documents and computer uploads together", () => {
    renderInfo([
      makeDocument(1, "drive.pdf"),
      makeComputerFile("upload-1", "notes.txt"),
      makeComputerFile("upload-2", "outline.pdf"),
    ]);

    expect(screen.getByText("3 files attached")).toBeInTheDocument();
  });

  it("underlines the file count", () => {
    renderInfo([makeDocument(1, "test.pdf")]);

    expect(screen.getByText("1 file attached")).toHaveClass("underline");
  });

  it("lists every attached file's name when opened", async () => {
    const user = userEvent.setup();
    renderInfo([makeDocument(1, "drive.pdf"), makeComputerFile("upload-1", "notes.txt")]);

    await user.click(screen.getByText("2 files attached"));

    expect(screen.getByText("drive.pdf")).toBeInTheDocument();
    expect(screen.getByText("notes.txt")).toBeInTheDocument();
  });

  it("shortens a long file name and ends it with an ellipsis", async () => {
    const user = userEvent.setup();
    renderInfo([makeDocument(1, "a".repeat(35))]);

    await user.click(screen.getByText("1 file attached"));

    const expectedText = "a".repeat(DOCUMENT_DISPLAY_NAME_MAX_CHARS - 1) + "…";
    expect(screen.getByText(expectedText)).toBeInTheDocument();
  });

  it("shows a remove button for every listed file", async () => {
    const user = userEvent.setup();
    renderInfo([makeDocument(1, "drive.pdf"), makeComputerFile("upload-1", "notes.txt")]);

    await user.click(screen.getByText("2 files attached"));

    expect(screen.getAllByTitle(composeEn.compose.removeAttachedFile)).toHaveLength(2);
  });

  it("hands the clicked file to onRemoveFile", async () => {
    const user = userEvent.setup();
    const computerFile = makeComputerFile("upload-1", "notes.txt");
    renderInfo([makeDocument(1, "drive.pdf"), computerFile]);

    await user.click(screen.getByText("2 files attached"));
    await user.click(screen.getAllByTitle(composeEn.compose.removeAttachedFile)[1]);

    expect(onRemoveFile).toHaveBeenCalledWith(computerFile);
  });
});
