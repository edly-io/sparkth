import { api, ApiRequestError, type Schema } from "@/lib/api";

export type ConnectionStatus = Schema<"GoogleDriveConnectionStatusResponse">;
export type DriveFolder = Schema<"DriveFolderResponse">;
export type DriveFile = Schema<"DriveFileResponse">;
export type DriveFolderWithFiles = Schema<"DriveFolderWithFilesResponse">;
export type DriveBrowseItem = Schema<"DriveBrowseItem">;
export type DriveBrowseResponse = Schema<"DriveBrowseResponse">;
export type SyncStatus = Schema<"SyncStatusResponse">;
export type FileRagStatus = Schema<"FileRagStatusResponse">;
export type FolderRagStatusResponse = Schema<"FolderRagStatusResponse">;

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

// TODO: rename the frontend's RagStatus terminology to match the backend's
// Document API naming (DocumentStatus) in a follow-up, separate from this
// mechanical client conversion.
//
// The generated client only emits types (erased at runtime), so the runtime
// values live here; `satisfies` checks them against the generated union, so
// any backend enum change fails the type check after regeneration.
export const RagStatus = {
  Queued: "queued",
  Processing: "processing",
  Ready: "ready",
  Failed: "failed",
} as const satisfies Record<string, Schema<"DocumentStatus">>;
export type RagStatus = Schema<"DocumentStatus">;

function bearer(token: string): { Authorization: string } {
  return { Authorization: `Bearer ${token}` };
}

// This module's public contract is plain Error objects with action-prefixed
// messages (logged before throwing); network failures propagate untouched.
function toError(prefix: string, error: unknown): never {
  if (error instanceof ApiRequestError) {
    const message = `${prefix}: ${error.message}`;
    console.error(message);
    throw new Error(message);
  }
  throw error;
}

// OAuth functions
export async function getConnectionStatus(token: string): Promise<ConnectionStatus> {
  try {
    const { data } = await api.GET("/api/v1/google-drive/oauth/status", {
      headers: bearer(token),
    });
    return data as ConnectionStatus;
  } catch (error) {
    toError("Failed to get connection status", error);
  }
}

export async function getAuthorizationUrl(token: string): Promise<string> {
  try {
    const { data } = await api.GET("/api/v1/google-drive/oauth/authorize", {
      headers: bearer(token),
    });
    return (data as Schema<"GoogleDriveAuthorizationUrlResponse">).url;
  } catch (error) {
    toError("Failed to get authorization URL", error);
  }
}

export async function disconnectGoogle(token: string): Promise<void> {
  try {
    await api.DELETE("/api/v1/google-drive/oauth/disconnect", { headers: bearer(token) });
  } catch (error) {
    toError("Failed to disconnect Google Drive", error);
  }
}

/**
 * Fetch all pages from a paginated endpoint, collecting every item.
 */
export async function fetchAllPages<T>(
  fetcher: (skip: number, limit: number) => Promise<PaginatedResponse<T>>,
  limit = 100,
): Promise<T[]> {
  const items: T[] = [];
  let skip = 0;
  let total = 0;
  do {
    const page = await fetcher(skip, limit);
    items.push(...page.items);
    total = page.total;
    skip += limit;
  } while (skip < total);
  return items;
}

// Folder functions
export async function listFolders(
  token: string,
  skip = 0,
  limit = 20,
): Promise<PaginatedResponse<DriveFolder>> {
  try {
    const { data } = await api.GET("/api/v1/google-drive/folders", {
      params: { query: { skip, limit } },
      headers: bearer(token),
    });
    return data as PaginatedResponse<DriveFolder>;
  } catch (error) {
    toError("Failed to list folders", error);
  }
}

export async function syncFolder(driveFolderId: string, token: string): Promise<DriveFolder> {
  try {
    const { data } = await api.POST("/api/v1/google-drive/folders/sync", {
      body: { drive_folder_id: driveFolderId },
      headers: bearer(token),
    });
    return data as DriveFolder;
  } catch (error) {
    toError("Failed to sync folder", error);
  }
}

export async function createFolder(
  name: string,
  parentId: string | undefined,
  token: string,
): Promise<DriveFolder> {
  try {
    const { data } = await api.POST("/api/v1/google-drive/folders", {
      body: { name, parent_id: parentId },
      headers: bearer(token),
    });
    return data as DriveFolder;
  } catch (error) {
    toError("Failed to create folder", error);
  }
}

export async function getFolder(folderId: number, token: string): Promise<DriveFolderWithFiles> {
  try {
    const { data } = await api.GET("/api/v1/google-drive/folders/{folder_id}", {
      params: { path: { folder_id: folderId } },
      headers: bearer(token),
    });
    return data as DriveFolderWithFiles;
  } catch (error) {
    toError("Failed to get folder", error);
  }
}

export async function removeFolder(folderId: number, token: string): Promise<void> {
  try {
    await api.DELETE("/api/v1/google-drive/folders/{folder_id}", {
      params: { path: { folder_id: folderId } },
      headers: bearer(token),
    });
  } catch (error) {
    toError("Failed to remove folder", error);
  }
}

export async function refreshFolder(folderId: number, token: string): Promise<SyncStatus> {
  try {
    const { data } = await api.POST("/api/v1/google-drive/folders/{folder_id}/refresh", {
      params: { path: { folder_id: folderId } },
      headers: bearer(token),
    });
    return data as SyncStatus;
  } catch (error) {
    toError("Failed to refresh folder", error);
  }
}

// File functions
export async function listFiles(
  folderId: number,
  token: string,
  skip = 0,
  limit = 20,
): Promise<PaginatedResponse<DriveFile>> {
  try {
    const { data } = await api.GET("/api/v1/google-drive/folders/{folder_id}/files", {
      params: { path: { folder_id: folderId }, query: { skip, limit } },
      headers: bearer(token),
    });
    return data as PaginatedResponse<DriveFile>;
  } catch (error) {
    toError("Failed to list files", error);
  }
}

export async function uploadFile(folderId: number, file: File, token: string): Promise<DriveFile> {
  try {
    const { data } = await api.POST("/api/v1/google-drive/folders/{folder_id}/files", {
      params: { path: { folder_id: folderId } },
      body: { file: "" },
      bodySerializer: () => {
        const formData = new FormData();
        formData.append("file", file);
        return formData;
      },
      // Content-Type must stay unset so fetch adds the multipart boundary.
      headers: { "Content-Type": null, ...bearer(token) },
    });
    return data as DriveFile;
  } catch (error) {
    toError("Failed to upload file", error);
  }
}

export async function downloadFile(fileId: number, token: string): Promise<Blob> {
  try {
    const { data } = await api.GET("/api/v1/google-drive/files/{file_id}/download", {
      params: { path: { file_id: fileId } },
      parseAs: "blob",
      headers: bearer(token),
    });
    return data as Blob;
  } catch (error) {
    toError("Failed to download file", error);
  }
}

export async function renameFile(
  fileId: number,
  newName: string,
  token: string,
): Promise<DriveFile> {
  try {
    const { data } = await api.PATCH("/api/v1/google-drive/files/{file_id}", {
      params: { path: { file_id: fileId } },
      body: { name: newName },
      headers: bearer(token),
    });
    return data as DriveFile;
  } catch (error) {
    toError("Failed to rename file", error);
  }
}

export async function deleteFile(fileId: number, token: string): Promise<void> {
  try {
    await api.DELETE("/api/v1/google-drive/files/{file_id}", {
      params: { path: { file_id: fileId } },
      headers: bearer(token),
    });
  } catch (error) {
    toError("Failed to delete file", error);
  }
}

// Browse functions
export async function browseDrive(
  parentId: string | undefined,
  token: string,
): Promise<DriveBrowseResponse> {
  try {
    const { data } = await api.GET("/api/v1/google-drive/browse", {
      params: { query: parentId ? { folder_id: parentId } : undefined },
      headers: bearer(token),
    });
    return data as DriveBrowseResponse;
  } catch (error) {
    toError("Failed to browse Drive", error);
  }
}

export async function getFolderRagStatus(
  folderId: number,
  token: string,
): Promise<FolderRagStatusResponse> {
  try {
    const { data } = await api.GET("/api/v1/google-drive/folders/{folder_id}/rag-status", {
      params: { path: { folder_id: folderId } },
      headers: bearer(token),
    });
    return data as FolderRagStatusResponse;
  } catch (error) {
    toError("Failed to get RAG status", error);
  }
}

// Helper functions
export function formatFileSize(bytes?: number | null): string {
  if (!bytes) return "-";
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`;
}

export function formatDate(dateString?: string | null): string {
  if (!dateString) return "-";
  return new Date(dateString).toLocaleDateString();
}
