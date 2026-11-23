import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { ATTACHMENT_SOURCES } from "@/plugins/compose/src/slots/attachments";
import { AttachedFilesInfo } from "@/plugins/compose/src/components/ui/attachment/AttachedFilesInfo";
import { TextAttachment } from "@/plugins/compose/src/types";
import { DOCUMENT_DISPLAY_NAME_MAX_CHARS } from "@/plugins/compose/src/displayName";
import composeEn from "@/plugins/compose/src/i18n/en.json";
import { renderWithIntl } from "@/lib/testing/intl";

describe("AttachedFilesInfo", () => {
  const onRemoveFile = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    ATTACHMENT_SOURCES.clear();
    ATTACHMENT_SOURCES.set("drive-plugin", [
      {
        id: "drive-source",
        label: "Pick from Drive",
        icon: () => <svg data-testid="drive-icon" />,
        loadPicker: () => Promise.resolve({ default: () => null }),
      },
    ]);
  });

  const makeDocument = (id: number, name: string): TextAttachment => ({
    name,
    text: "content",
    size: 1024,
    documentId: id,
    source: "drive-source",
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

  it("shows a remove button for a file already sent", async () => {
    const user = userEvent.setup();
    renderInfo([
      makeDocument(1, "drive.pdf"),
      { ...makeComputerFile("upload-1", "notes.txt"), isSent: true },
    ]);

    await user.click(screen.getByText("2 files attached"));

    expect(screen.getAllByTitle(composeEn.compose.removeAttachedFile)).toHaveLength(2);
  });

  it("shows no remove button for a file whose text is stored in a message", async () => {
    const user = userEvent.setup();
    renderInfo([
      makeDocument(1, "drive.pdf"),
      { ...makeComputerFile("message-5", "notes.txt"), isSent: true, isStoredInMessage: true },
    ]);

    await user.click(screen.getByText("2 files attached"));

    expect(screen.getAllByTitle(composeEn.compose.removeAttachedFile)).toHaveLength(1);
  });

  it("starts the row of a file that is uploading with a spinner", async () => {
    const user = userEvent.setup();
    renderInfo([{ ...makeComputerFile("upload-1", "notes.txt"), text: "", isUploading: true }]);

    await user.click(screen.getByText("1 file attached"));

    const spinner = screen.getByRole("status", { name: composeEn.compose.uploadingFile });
    const name = screen.getByText("notes.txt");
    expect(spinner.compareDocumentPosition(name) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("says which of the files waiting to be sent is uploading", () => {
    renderInfo([
      { ...makeComputerFile("upload-1", "sent.txt"), isSent: true },
      makeComputerFile("upload-2", "notes.txt"),
      { ...makeComputerFile("upload-3", "outline.txt"), text: "", isUploading: true },
      { ...makeComputerFile("upload-4", "week3.txt"), text: "", isUploading: true },
    ]);

    expect(screen.getByText("Uploading file (2 of 3)")).toBeInTheDocument();
  });

  it("shows no upload indicator once every file has uploaded", () => {
    renderInfo([makeComputerFile("upload-1", "notes.txt")]);

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("starts a document's row with its source's icon", async () => {
    const user = userEvent.setup();
    renderInfo([makeDocument(1, "drive.pdf")]);

    await user.click(screen.getByText("1 file attached"));

    expect(screen.getByRole("listitem")).toContainElement(screen.getByTestId("drive-icon"));
  });

  it("starts a computer file's row with the file icon", async () => {
    const user = userEvent.setup();
    renderInfo([makeComputerFile("upload-1", "notes.txt")]);

    await user.click(screen.getByText("1 file attached"));

    expect(screen.getByRole("listitem").querySelector(".lucide-file-text")).toBeInTheDocument();
  });

  it("shows the spinner in place of the icon while a file uploads", async () => {
    const user = userEvent.setup();
    renderInfo([{ ...makeComputerFile("upload-1", "notes.txt"), text: "", isUploading: true }]);

    await user.click(screen.getByText("1 file attached"));

    const row = screen.getByRole("listitem");
    expect(row.firstElementChild?.firstElementChild).toHaveAttribute("role", "status");
    expect(row.querySelector(".lucide-file-text")).not.toBeInTheDocument();
  });
});
