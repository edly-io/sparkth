import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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

import { getFolder, getFolderRagStatus } from "@/lib/drive";

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
    { file_id: 10, name: "doc.pdf", rag_status: "ready" as const },
    { file_id: 20, name: "notes.txt", rag_status: "processing" as const },
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

  it("shows status text as tooltip on hover", async () => {
    render(<FolderDetail folder={mockFolder} onClose={vi.fn()} onFolderChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("doc.pdf")).toBeInTheDocument();
    });

    const greenCircle = screen.getByTestId("rag-status-10");
    expect(greenCircle).toHaveAttribute("title", "ready");

    const yellowCircle = screen.getByTestId("rag-status-20");
    expect(yellowCircle).toHaveAttribute("title", "processing");
  });

  it("renders red circle for failed status", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [{ file_id: 10, name: "doc.pdf", rag_status: "failed" }],
    });

    render(<FolderDetail folder={mockFolder} onClose={vi.fn()} onFolderChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTestId("rag-status-10")).toHaveClass("bg-red-500");
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

  it("calls getFolderRagStatus on mount", async () => {
    render(<FolderDetail folder={mockFolder} onClose={vi.fn()} onFolderChange={vi.fn()} />);

    await waitFor(() => {
      expect(getFolderRagStatus).toHaveBeenCalledWith(1, "test-token");
    });
  });

  it("sets up polling interval and cleans up on unmount", () => {
    const setIntervalSpy = vi.spyOn(globalThis, "setInterval");
    const clearIntervalSpy = vi.spyOn(globalThis, "clearInterval");

    const { unmount } = render(
      <FolderDetail folder={mockFolder} onClose={vi.fn()} onFolderChange={vi.fn()} />,
    );

    // Verify setInterval was called with 5s interval
    const intervalCall = setIntervalSpy.mock.calls.find((call) => call[1] === 5000);
    expect(intervalCall).toBeDefined();

    unmount();

    // Verify clearInterval was called
    expect(clearIntervalSpy).toHaveBeenCalled();

    setIntervalSpy.mockRestore();
    clearIntervalSpy.mockRestore();
  });
});
