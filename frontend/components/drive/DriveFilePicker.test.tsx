import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DriveFilePicker from "./DriveFilePicker";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ token: "test-token" }),
}));

vi.mock("@/lib/drive", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/drive")>();
  return {
    ...actual,
    listFolders: vi.fn(),
    listFiles: vi.fn(),
    getFolderRagStatus: vi.fn(),
  };
});

import { listFolders, listFiles, getFolderRagStatus } from "@/lib/drive";

const mockFolder = {
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

const selectFolder = async () => {
  const folderButton = await screen.findByText("Test Folder");
  await userEvent.click(folderButton);
};

describe("DriveFilePicker - RAG Status Column", () => {
  beforeEach(() => {
    vi.mocked(listFolders).mockResolvedValue([mockFolder]);
    vi.mocked(listFiles).mockResolvedValue(mockFiles);
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [
        { file_id: 10, name: "doc.pdf", rag_status: "ready", rag_error: null },
        { file_id: 20, name: "notes.txt", rag_status: "processing", rag_error: null },
      ],
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders colored status circles for each file", async () => {
    render(<DriveFilePicker onClose={vi.fn()} onFileSelected={vi.fn()} />);
    await selectFolder();

    await waitFor(() => {
      expect(screen.getByTestId("rag-status-10")).toHaveClass("bg-green-500");
    });
    expect(screen.getByTestId("rag-status-20")).toHaveClass("bg-yellow-500");
  });

  it("renders red circle for failed status", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [{ file_id: 10, name: "doc.pdf", rag_status: "failed", rag_error: null }],
    });
    vi.mocked(listFiles).mockResolvedValue([mockFiles[0]]);

    render(<DriveFilePicker onClose={vi.fn()} onFileSelected={vi.fn()} />);
    await selectFolder();

    await waitFor(() => {
      expect(screen.getByTestId("rag-status-10")).toHaveClass("bg-red-500");
    });
  });

  it("renders gray circle for queued status", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [{ file_id: 10, name: "doc.pdf", rag_status: "queued", rag_error: null }],
    });
    vi.mocked(listFiles).mockResolvedValue([mockFiles[0]]);

    render(<DriveFilePicker onClose={vi.fn()} onFileSelected={vi.fn()} />);
    await selectFolder();

    await waitFor(() => {
      expect(screen.getByTestId("rag-status-10")).toHaveClass("bg-gray-300");
    });
  });

  it("renders gray circle for null status", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [{ file_id: 10, name: "doc.pdf", rag_status: null, rag_error: null }],
    });
    vi.mocked(listFiles).mockResolvedValue([mockFiles[0]]);

    render(<DriveFilePicker onClose={vi.fn()} onFileSelected={vi.fn()} />);
    await selectFolder();

    await waitFor(() => {
      expect(screen.getByTestId("rag-status-10")).toHaveClass("bg-gray-300");
    });
  });
});

describe("DriveFilePicker - Select Button Disabled State", () => {
  beforeEach(() => {
    vi.mocked(listFolders).mockResolvedValue([mockFolder]);
    vi.mocked(listFiles).mockResolvedValue(mockFiles);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("enables Select only when rag_status is ready", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [
        { file_id: 10, name: "doc.pdf", rag_status: "ready", rag_error: null },
        { file_id: 20, name: "notes.txt", rag_status: "processing", rag_error: null },
      ],
    });

    render(<DriveFilePicker onClose={vi.fn()} onFileSelected={vi.fn()} />);
    await selectFolder();

    await waitFor(() => {
      expect(screen.getByTestId("select-file-10")).not.toBeDisabled();
    });
    expect(screen.getByTestId("select-file-20")).toBeDisabled();
  });

  it("disables Select for queued files", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [{ file_id: 10, name: "doc.pdf", rag_status: "queued", rag_error: null }],
    });
    vi.mocked(listFiles).mockResolvedValue([mockFiles[0]]);

    render(<DriveFilePicker onClose={vi.fn()} onFileSelected={vi.fn()} />);
    await selectFolder();

    await waitFor(() => {
      expect(screen.getByTestId("select-file-10")).toBeDisabled();
    });
  });

  it("disables Select for failed files", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [{ file_id: 10, name: "doc.pdf", rag_status: "failed", rag_error: null }],
    });
    vi.mocked(listFiles).mockResolvedValue([mockFiles[0]]);

    render(<DriveFilePicker onClose={vi.fn()} onFileSelected={vi.fn()} />);
    await selectFolder();

    await waitFor(() => {
      expect(screen.getByTestId("select-file-10")).toBeDisabled();
    });
  });

  it("disables Select for null status", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [{ file_id: 10, name: "doc.pdf", rag_status: null, rag_error: null }],
    });
    vi.mocked(listFiles).mockResolvedValue([mockFiles[0]]);

    render(<DriveFilePicker onClose={vi.fn()} onFileSelected={vi.fn()} />);
    await selectFolder();

    await waitFor(() => {
      expect(screen.getByTestId("select-file-10")).toBeDisabled();
    });
  });

  it("calls onFileSelected when ready file is selected", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [{ file_id: 10, name: "doc.pdf", rag_status: "ready", rag_error: null }],
    });
    vi.mocked(listFiles).mockResolvedValue([mockFiles[0]]);

    const onFileSelected = vi.fn();
    render(<DriveFilePicker onClose={vi.fn()} onFileSelected={onFileSelected} />);
    await selectFolder();

    const button = await screen.findByTestId("select-file-10");
    await waitFor(() => expect(button).not.toBeDisabled());
    await userEvent.click(button);

    expect(onFileSelected).toHaveBeenCalledWith(
      expect.objectContaining({ id: 10, name: "doc.pdf" }),
    );
  });
});

describe("DriveFilePicker - RAG Status Polling", () => {
  beforeEach(() => {
    vi.mocked(listFolders).mockResolvedValue([mockFolder]);
    vi.mocked(listFiles).mockResolvedValue(mockFiles);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls getFolderRagStatus on folder open", async () => {
    vi.mocked(getFolderRagStatus).mockResolvedValue({
      folder_id: 1,
      files: [{ file_id: 10, name: "doc.pdf", rag_status: "ready", rag_error: null }],
    });

    render(<DriveFilePicker onClose={vi.fn()} onFileSelected={vi.fn()} />);
    await selectFolder();

    await waitFor(() => {
      expect(getFolderRagStatus).toHaveBeenCalledWith(1, "test-token");
    });
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

    render(<DriveFilePicker onClose={vi.fn()} onFileSelected={vi.fn()} />);
    await selectFolder();

    await waitFor(() => {
      expect(screen.getByTestId("rag-status-10")).toHaveClass("bg-green-500");
    });

    const pollTimeout = setTimeoutSpy.mock.calls.find((call) => call[1] === 5000);
    expect(pollTimeout).toBeUndefined();

    setTimeoutSpy.mockRestore();
  });
});
