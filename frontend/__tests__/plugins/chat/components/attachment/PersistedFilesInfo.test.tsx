import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { PersistedFilesInfo } from "@/plugins/chat/components/attachment/PersistedFilesInfo";
import { TextAttachment } from "@/plugins/chat/types";
import { RAG_DISPLAY_NAME_MAX_CHARS } from "@/lib/utils";

describe("PersistedFilesInfo", () => {
  const mockOnDetachFile = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  const makeDriveFile = (id: number, name: string): TextAttachment => ({
    name,
    text: "content",
    size: 1024,
    driveFileDbId: id,
  });

  it("renders null when no Drive-file attachments", () => {
    const { container } = render(
      <PersistedFilesInfo attachments={[]} onDetachFile={mockOnDetachFile} />,
    );

    expect(container.firstChild).toBeNull();
  });

  it("renders null when attachments array is empty", () => {
    const { container } = render(
      <PersistedFilesInfo attachments={[]} onDetachFile={mockOnDetachFile} />,
    );

    expect(container.firstChild).toBeNull();
  });

  it("renders info line with correct file count (single file)", () => {
    const attachments: TextAttachment[] = [makeDriveFile(1, "test.pdf")];

    render(<PersistedFilesInfo attachments={attachments} onDetachFile={mockOnDetachFile} />);

    expect(screen.getByText("1 file")).toBeInTheDocument();
    expect(screen.getByText("will be read for relevant context")).toBeInTheDocument();
  });

  it("renders info line with correct file count (multiple files)", () => {
    const attachments: TextAttachment[] = [
      makeDriveFile(1, "test1.pdf"),
      makeDriveFile(2, "test2.pdf"),
      makeDriveFile(3, "test3.pdf"),
    ];

    render(<PersistedFilesInfo attachments={attachments} onDetachFile={mockOnDetachFile} />);

    expect(screen.getByText("3 files")).toBeInTheDocument();
    expect(screen.getByText("will be read for relevant context")).toBeInTheDocument();
  });

  it('"n files" trigger text is underlined', () => {
    const attachments: TextAttachment[] = [makeDriveFile(1, "test.pdf")];

    render(<PersistedFilesInfo attachments={attachments} onDetachFile={mockOnDetachFile} />);

    const trigger = screen.getByText("1 file");
    expect(trigger).toHaveClass("underline");
  });

  it("popover lists all Drive-file names on open", async () => {
    const user = userEvent.setup();
    const attachments: TextAttachment[] = [
      makeDriveFile(1, "first.pdf"),
      makeDriveFile(2, "second.pdf"),
    ];

    render(<PersistedFilesInfo attachments={attachments} onDetachFile={mockOnDetachFile} />);

    await user.click(screen.getByText("2 files"));

    expect(screen.getByText("first.pdf")).toBeInTheDocument();
    expect(screen.getByText("second.pdf")).toBeInTheDocument();
  });

  it("truncates long filenames using RAG_DISPLAY_NAME_MAX_CHARS", async () => {
    const user = userEvent.setup();
    const longName = "a".repeat(35);
    const attachments: TextAttachment[] = [makeDriveFile(1, longName)];

    render(<PersistedFilesInfo attachments={attachments} onDetachFile={mockOnDetachFile} />);

    await user.click(screen.getByText("1 file"));

    const expectedText = "a".repeat(RAG_DISPLAY_NAME_MAX_CHARS - 1) + "…";
    expect(screen.getByText(expectedText)).toBeInTheDocument();
  });

  it("calls onDetachFile with the correct driveFileDbId on × click", async () => {
    const user = userEvent.setup();
    const attachments: TextAttachment[] = [
      makeDriveFile(1, "first.pdf"),
      makeDriveFile(2, "second.pdf"),
    ];

    render(<PersistedFilesInfo attachments={attachments} onDetachFile={mockOnDetachFile} />);

    await user.click(screen.getByText("2 files"));

    // Find and click the × button for the second file
    const removeButtons = screen.getAllByTitle("Remove file");
    await user.click(removeButtons[1]);

    expect(mockOnDetachFile).toHaveBeenCalledWith(2);
  });

  it("renders × button for every listed file", async () => {
    const user = userEvent.setup();
    const attachments: TextAttachment[] = [
      makeDriveFile(1, "first.pdf"),
      makeDriveFile(2, "second.pdf"),
    ];

    render(<PersistedFilesInfo attachments={attachments} onDetachFile={mockOnDetachFile} />);

    await user.click(screen.getByText("2 files"));

    const removeButtons = screen.getAllByTitle("Remove file");
    expect(removeButtons).toHaveLength(2);
  });

  it("does not render when only non-Drive attachments are present", () => {
    const attachments: TextAttachment[] = [{ name: "test.txt", text: "content", size: 512 }];

    const { container } = render(
      <PersistedFilesInfo attachments={attachments} onDetachFile={mockOnDetachFile} />,
    );

    expect(container.firstChild).toBeNull();
  });
});
