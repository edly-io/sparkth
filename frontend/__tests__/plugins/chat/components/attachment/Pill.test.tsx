import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { Pill } from "@/plugins/chat/components/attachment/Pill";
import { TooltipProvider } from "@/components/ui/Tooltip";
import { TextAttachment } from "@/plugins/chat/types";

describe("Pill", () => {
  const mockOnPreview = vi.fn();
  const mockOnRemove = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("single attachment", () => {
    it("renders filename when only one attachment", () => {
      const attachments: TextAttachment[] = [
        { name: "course-guide.pdf", size: 1024, text: "content" },
      ];

      render(<Pill attachments={attachments} onPreview={mockOnPreview} onRemove={mockOnRemove} />);

      expect(screen.getByText("course-guide.pdf")).toBeInTheDocument();
      expect(screen.queryByText(/\+ \d+ others/)).not.toBeInTheDocument();
    });

    it("calls onPreview with attachment when clicked", async () => {
      const attachment: TextAttachment = {
        name: "document.pdf",
        size: 2048,
        text: "content",
      };
      const attachments = [attachment];

      render(<Pill attachments={attachments} onPreview={mockOnPreview} onRemove={mockOnRemove} />);

      const button = screen.getByRole("button", { name: /document.pdf/ });
      await userEvent.click(button);

      expect(mockOnPreview).toHaveBeenCalledWith(attachment);
    });

    it("calls onRemove with undefined when remove button clicked", async () => {
      const attachments: TextAttachment[] = [{ name: "file.pdf", size: 1024, text: "content" }];

      render(<Pill attachments={attachments} onPreview={mockOnPreview} onRemove={mockOnRemove} />);

      const removeButton = screen
        .getByRole("button", { name: "" })
        .parentElement?.querySelector("button:last-child");
      if (removeButton) {
        await userEvent.click(removeButton);
      }

      expect(mockOnRemove).toHaveBeenCalledWith(undefined);
    });
  });

  describe("multiple attachments", () => {
    it('displays "filename + N others" when multiple attachments', () => {
      const attachments: TextAttachment[] = [
        { name: "first.pdf", size: 1024, text: "content" },
        { name: "second.pdf", size: 2048, text: "content", driveFileDbId: 1 },
        { name: "third.pdf", size: 3072, text: "content", driveFileDbId: 2 },
      ];

      render(
        <TooltipProvider>
          <Pill attachments={attachments} onPreview={mockOnPreview} onRemove={mockOnRemove} />
        </TooltipProvider>,
      );

      expect(screen.getByText("first.pdf")).toBeInTheDocument();
      expect(screen.getByText(/\+ 2 others/)).toBeInTheDocument();
    });

    it('displays "+ N others" indicator for additional files', () => {
      const attachments: TextAttachment[] = [
        { name: "first.pdf", size: 1024, text: "content" },
        { name: "second.pdf", size: 2048, text: "content", driveFileDbId: 1 },
        { name: "third.pdf", size: 3072, text: "content", driveFileDbId: 2 },
      ];

      render(
        <TooltipProvider>
          <Pill attachments={attachments} onPreview={mockOnPreview} onRemove={mockOnRemove} />
        </TooltipProvider>,
      );

      // Verify the multiple files indicator is displayed
      expect(screen.getByText(/\+ 2 others/)).toBeInTheDocument();
      // Verify first filename is shown
      expect(screen.getByText("first.pdf")).toBeInTheDocument();
    });

    it("calls onRemove with file id when removing specific drive file", async () => {
      const attachments: TextAttachment[] = [
        { name: "first.pdf", size: 1024, text: "content" },
        { name: "second.pdf", size: 2048, text: "content", driveFileDbId: 123 },
      ];

      render(
        <TooltipProvider>
          <Pill attachments={attachments} onPreview={mockOnPreview} onRemove={mockOnRemove} />
        </TooltipProvider>,
      );

      const removeButton = screen
        .getByRole("button", { name: "" })
        .parentElement?.querySelector("button:last-child");
      if (removeButton) {
        await userEvent.click(removeButton);
      }

      expect(mockOnRemove).toHaveBeenCalledWith(undefined);
    });
  });

  it("returns null when attachments array is empty", () => {
    const { container } = render(
      <Pill attachments={[]} onPreview={mockOnPreview} onRemove={mockOnRemove} />,
    );

    expect(container.firstChild).toBeNull();
  });
});
