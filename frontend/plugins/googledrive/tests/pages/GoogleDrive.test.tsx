import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { TooltipProvider } from "@/lib/components/ui/Tooltip";
import GoogleDrive from "@/plugins/googledrive/src/pages/GoogleDrive";
import { listFiles, listFolders, refreshFolder } from "@/plugins/googledrive/src/client";
import type { DriveFile, DriveFolder } from "@/plugins/googledrive/src/types";

vi.mock("@/lib/auth/hooks", () => ({ useAuth: () => ({ token: "t" }) }));

vi.mock("@/plugins/googledrive/src/client", () => ({
  getConnectionStatus: vi.fn(async () => ({ connected: true, email: "a@example.com" })),
  fetchAllPages: vi.fn(async (fetchPage) => (await fetchPage(0, 100)).items),
  listFolders: vi.fn(),
  listFiles: vi.fn(),
  refreshFolder: vi.fn(),
  getFolderDocumentStatus: vi.fn(async () => ({ files: [] })),
  downloadFile: vi.fn(),
  deleteFile: vi.fn(),
}));

function buildFolder(id: number): DriveFolder {
  return {
    id,
    drive_folder_id: `drive-${id}`,
    name: `Folder ${id}`,
    parent_id: null,
    file_count: 1,
    last_synced_at: "2026-11-12T10:00:00Z",
    sync_status: "synced",
  };
}

function buildFile(id: number): DriveFile {
  return {
    id,
    drive_file_id: `drive-file-${id}`,
    name: `file-${id}.pdf`,
    mime_type: "application/pdf",
    rag_status: "ready",
  };
}

describe("GoogleDrive re-sync", () => {
  beforeEach(() => {
    vi.mocked(listFolders).mockImplementation(async () => ({
      items: [buildFolder(1), buildFolder(2)],
      total: 2,
      skip: 0,
      limit: 100,
    }));
    vi.mocked(listFiles).mockImplementation(async (folderId: number) => ({
      items: [buildFile(folderId)],
      total: 1,
      skip: 0,
      limit: 10,
    }));
  });

  it("keeps the failure message after the file list reloads", async () => {
    vi.mocked(refreshFolder)
      .mockResolvedValueOnce({ folder_id: 1, sync_status: "synced" })
      .mockRejectedValueOnce(new Error("Request failed (HTTP 500)"));
    render(
      <TooltipProvider>
        <GoogleDrive />
      </TooltipProvider>,
    );
    await screen.findByText("file-2.pdf");

    await userEvent.click(screen.getByRole("button", { name: "Re-sync" }));

    await waitFor(() => expect(listFolders).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("file-2.pdf")).toBeInTheDocument();
    expect(screen.getByText("Re-sync failed for 1 of 2 folder(s)")).toBeInTheDocument();
  });
});
