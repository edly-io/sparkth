import { api, ApiRequestError, bearer, type Schema } from "@/lib/api";
import type {
  ConnectionStatus,
  DriveBrowseResponse,
  DriveFolder,
  FolderDocumentStatusResponse,
  PaginatedFiles,
  PaginatedFolders,
  SyncStatus,
} from "@/plugins/google-drive/types";

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
 *
 * The fetcher parameter is structural (just the envelope fields the loop
 * reads), so any of the generated PaginatedResponse_* shapes satisfies it.
 */
export async function fetchAllPages<T>(
  fetcher: (skip: number, limit: number) => Promise<{ items: T[]; total: number }>,
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
export async function listFolders(token: string, skip = 0, limit = 20): Promise<PaginatedFolders> {
  try {
    const { data } = await api.GET("/api/v1/google-drive/folders", {
      params: { query: { skip, limit } },
      headers: bearer(token),
    });
    return data as PaginatedFolders;
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
): Promise<PaginatedFiles> {
  try {
    const { data } = await api.GET("/api/v1/google-drive/folders/{folder_id}/files", {
      params: { path: { folder_id: folderId }, query: { skip, limit } },
      headers: bearer(token),
    });
    return data as PaginatedFiles;
  } catch (error) {
    toError("Failed to list files", error);
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

export async function getFolderDocumentStatus(
  folderId: number,
  token: string,
): Promise<FolderDocumentStatusResponse> {
  try {
    const { data } = await api.GET("/api/v1/google-drive/folders/{folder_id}/rag-status", {
      params: { path: { folder_id: folderId } },
      headers: bearer(token),
    });
    return data as FolderDocumentStatusResponse;
  } catch (error) {
    toError("Failed to get document status", error);
  }
}
