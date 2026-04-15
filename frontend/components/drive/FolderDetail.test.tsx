import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import FolderDetail from "./FolderDetail";
import type { DriveFolder } from "@/lib/drive";

// Mock auth context
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ token: "test-token" }),
}));

// Mock drive API functions
vi.mock("@/lib/drive", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/drive")>();
  return {
    ...actual,
    getFolder: vi.fn(),
    getFolderRagStatus: vi.fn(),
    refreshFolder: vi.fn(),
  };
});

import { getFolder, getFolderRagStatus, refreshFolder } from "@/lib/drive";

const mockFolder: DriveFolder = {
  id: 1,
  drive_folder_id: "abc123",
  name: "Test Folder",
  file_count: 2,
  sync_status: "synced",
};

const mockFiles = [
  { id: 10, drive_file_id: "f1", name: "doc.pdf", size: 1024, modified_time: "2026-01-01" },
  { id: 20, drive_file_id: "f2", name: "notes.txt", size: 512, modified_time: "2026-01-02" },
];

const mockRagStatuses = {
  folder_id: 1,
  files: [
    { file_id: 10, name: "doc.pdf", rag_status: "ready" as const, rag_error: null },
    { file_id: 20, name: "notes.txt", rag_status: "processing" as const, rag_error: null },
  ],
};

describe("FolderDetail - RAG Status Column", () => {
  beforeEach(() => {
    vi.mocked(getFolder).mockResolvedValue({ ...mockFolder, files: mockFiles });
    vi.mocked(getFolderRagStatus).mockResolvedValue(mockRagStatuses);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders a Status column header", async () => {
    render(<FolderDetail folder={mockFolder} onClose={vi.fn()} onFolderChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("Status")).toBeInTheDocument();
    });
  });

  it("renders colored status circles for each file", async () => {
    render(<FolderDetail folder={mockFolder} onClose={vi.fn()} onFolderChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("doc.pdf")).toBeInTheDocument();
    });

    const greenCircle = screen.getByTestId("rag-status-10");
    expect(greenCircle).toHaveClass("bg-green-500");

    const yellowCircle = screen.getByTestId("rag-status-20");
    expect(yellowCircle).toHaveClass("bg-yellow-500");
  });

  it("renders red circle for failed status", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [{ file_id: 10, name: "doc.pdf", rag_status: "failed", rag_error: null }],
    });

    render(<FolderDetail folder={mockFolder} onClose={vi.fn()} onFolderChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTestId("rag-status-10")).toHaveClass("bg-red-500");
    });
  });

  it("renders gray circle for null status", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [{ file_id: 10, name: "doc.pdf", rag_status: null, rag_error: null }],
    });

    render(<FolderDetail folder={mockFolder} onClose={vi.fn()} onFolderChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTestId("rag-status-10")).toHaveClass("bg-gray-300");
    });
  });

  it("renders gray circle for queued status", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [{ file_id: 10, name: "doc.pdf", rag_status: "queued" as const, rag_error: null }],
    });

    render(<FolderDetail folder={mockFolder} onClose={vi.fn()} onFolderChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTestId("rag-status-10")).toHaveClass("bg-gray-300");
    });
  });

  it("shows Queued text in tooltip for queued status", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [{ file_id: 10, name: "doc.pdf", rag_status: "queued" as const, rag_error: null }],
    });

    render(<FolderDetail folder={mockFolder} onClose={vi.fn()} onFolderChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("doc.pdf")).toBeInTheDocument();
    });

    const circle = screen.getByTestId("rag-status-10");
    await userEvent.hover(circle);

    await waitFor(() => {
      expect(screen.getByTestId("rag-tooltip-10")).toHaveTextContent("Queued");
    });
  });

  it("shows Queued text in tooltip for null status", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [{ file_id: 10, name: "doc.pdf", rag_status: null, rag_error: null }],
    });

    render(<FolderDetail folder={mockFolder} onClose={vi.fn()} onFolderChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("doc.pdf")).toBeInTheDocument();
    });

    const circle = screen.getByTestId("rag-status-10");
    await userEvent.hover(circle);

    await waitFor(() => {
      expect(screen.getByTestId("rag-tooltip-10")).toHaveTextContent("Queued");
    });
  });

  it("shows capitalized status text in tooltip div on hover", async () => {
    render(<FolderDetail folder={mockFolder} onClose={vi.fn()} onFolderChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("doc.pdf")).toBeInTheDocument();
    });

    const circle = screen.getByTestId("rag-status-10");
    await userEvent.hover(circle);

    await waitFor(() => {
      expect(screen.getByTestId("rag-tooltip-10")).toBeInTheDocument();
      expect(screen.getByTestId("rag-tooltip-10")).toHaveTextContent("Ready");
    });
  });

  it("hides tooltip div when not hovering", async () => {
    render(<FolderDetail folder={mockFolder} onClose={vi.fn()} onFolderChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("doc.pdf")).toBeInTheDocument();
    });

    expect(screen.queryByTestId("rag-tooltip-10")).not.toBeInTheDocument();
  });

  it("shows error reason in tooltip for failed files", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [
        {
          file_id: 10,
          name: "doc.pdf",
          rag_status: "failed",
          rag_error: "Download failed: 403 Forbidden",
        },
      ],
    });

    render(<FolderDetail folder={mockFolder} onClose={vi.fn()} onFolderChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("doc.pdf")).toBeInTheDocument();
    });

    const circle = screen.getByTestId("rag-status-10");
    await userEvent.hover(circle);

    await waitFor(() => {
      const tooltip = screen.getByTestId("rag-tooltip-10");
      expect(tooltip).toHaveTextContent("Failed");
      expect(tooltip).toHaveTextContent("Download failed: 403 Forbidden");
    });
  });
});

describe("FolderDetail - RAG Status Polling", () => {
  beforeEach(() => {
    vi.mocked(getFolder).mockResolvedValue({ ...mockFolder, files: mockFiles });
    vi.mocked(getFolderRagStatus).mockResolvedValue(mockRagStatuses);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("stops polling when all files reach terminal state", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [
        { file_id: 10, name: "doc.pdf", rag_status: "ready", rag_error: null },
        { file_id: 20, name: "notes.txt", rag_status: "failed", rag_error: "error" },
      ],
    });

    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");

    render(<FolderDetail folder={mockFolder} onClose={vi.fn()} onFolderChange={vi.fn()} />);

    // Wait for initial fetch to resolve — status circles should appear
    await waitFor(() => {
      expect(screen.getByTestId("rag-status-10")).toHaveClass("bg-green-500");
    });

    // All terminal — no poll setTimeout with 5000 should be scheduled
    const pollTimeout = setTimeoutSpy.mock.calls.find((call) => call[1] === 5000);
    expect(pollTimeout).toBeUndefined();

    setTimeoutSpy.mockRestore();
  });

  it("calls getFolderRagStatus on mount", async () => {
    render(<FolderDetail folder={mockFolder} onClose={vi.fn()} onFolderChange={vi.fn()} />);

    await waitFor(() => {
      expect(getFolderRagStatus).toHaveBeenCalledWith(1, "test-token");
    });
  });

  it("restarts polling after sync when all files were terminal", async () => {
    vi.mocked(refreshFolder).mockResolvedValue({ folder_id: 1, sync_status: "synced" });
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [{ file_id: 10, name: "doc.pdf", rag_status: "ready", rag_error: null }],
    });

    render(<FolderDetail folder={mockFolder} onClose={vi.fn()} onFolderChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTestId("rag-status-10")).toHaveClass("bg-green-500");
    });

    const callsBefore = vi.mocked(getFolderRagStatus).mock.calls.length;

    const syncButton = screen.getByLabelText("Sync folder");
    await userEvent.click(syncButton);

    await waitFor(() => {
      expect(vi.mocked(getFolderRagStatus).mock.calls.length).toBeGreaterThan(callsBefore);
    });
  });

  it("uses setTimeout for polling and clears on unmount", async () => {
    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
    const clearTimeoutSpy = vi.spyOn(globalThis, "clearTimeout");

    const { unmount } = render(
      <FolderDetail folder={mockFolder} onClose={vi.fn()} onFolderChange={vi.fn()} />,
    );

    // Wait for initial fetch to complete so setTimeout gets scheduled
    await waitFor(() => {
      const timeoutCall = setTimeoutSpy.mock.calls.find((call) => call[1] === 5000);
      expect(timeoutCall).toBeDefined();
    });

    unmount();

    expect(clearTimeoutSpy).toHaveBeenCalled();

    setTimeoutSpy.mockRestore();
    clearTimeoutSpy.mockRestore();
  });
});
