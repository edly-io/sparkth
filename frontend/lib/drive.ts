const API_BASE_URL = "/api/v1/googledrive";

export interface ConnectionStatus {
  connected: boolean;
  email?: string;
  expires_at?: string;
}

export interface DriveFolder {
  id: number;
  drive_folder_id: string;
  name: string;
  parent_id?: string;
  file_count: number;
  last_synced_at?: string;
  sync_status: string;
}

export interface DriveFile {
  id: number;
  drive_file_id: string;
  name: string;
  mime_type?: string;
  size?: number;
  modified_time?: string;
  last_synced_at?: string;
}

export interface DriveFolderWithFiles extends DriveFolder {
  files: DriveFile[];
}

export interface DriveBrowseItem {
  id: string;
  name: string;
  mime_type: string;
  is_folder: boolean;
  modified_time?: string;
  size?: number;
}

export interface SyncStatus {
  folder_id: number;
  sync_status: string;
  last_synced_at?: string;
  error?: string;
}

async function handleError(message: string, response: Response) {
  const text = await response.text();
  const error = `${message}: ${text}`;
  console.error(error);
  throw new Error(error);
}

// OAuth functions
export async function getConnectionStatus(token: string): Promise<ConnectionStatus> {
  const response = await fetch(`${API_BASE_URL}/oauth/status`, {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    await handleError("Failed to get connection status", response);
  }

  return response.json();
}

export async function getAuthorizationUrl(token: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/oauth/authorize`, {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    await handleError("Failed to get authorization URL", response);
  }

  const data = await response.json();
  return data.url;
}

export async function disconnectGoogle(token: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/oauth/disconnect`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    await handleError("Failed to disconnect Google Drive", response);
  }
}

// Folder functions
export async function listFolders(token: string): Promise<DriveFolder[]> {
  const response = await fetch(`${API_BASE_URL}/folders`, {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    await handleError("Failed to list folders", response);
  }

  return response.json();
}

export async function syncFolder(driveFolderId: string, token: string): Promise<DriveFolder> {
  const response = await fetch(`${API_BASE_URL}/folders/sync`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ drive_folder_id: driveFolderId }),
  });

  if (!response.ok) {
    await handleError("Failed to sync folder", response);
  }

  return response.json();
}

export async function createFolder(
  name: string,
  parentId: string | undefined,
  token: string
): Promise<DriveFolder> {
  const response = await fetch(`${API_BASE_URL}/folders`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ name, parent_id: parentId }),
  });

  if (!response.ok) {
    await handleError("Failed to create folder", response);
  }

  return response.json();
}

export async function getFolder(folderId: number, token: string): Promise<DriveFolderWithFiles> {
  const response = await fetch(`${API_BASE_URL}/folders/${folderId}`, {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    await handleError("Failed to get folder", response);
  }

  return response.json();
}

export async function removeFolder(folderId: number, token: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/folders/${folderId}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    await handleError("Failed to remove folder", response);
  }
}

export async function refreshFolder(folderId: number, token: string): Promise<SyncStatus> {
  const response = await fetch(`${API_BASE_URL}/folders/${folderId}/refresh`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    await handleError("Failed to refresh folder", response);
  }

  return response.json();
}

// File functions
export async function listFiles(folderId: number, token: string): Promise<DriveFile[]> {
  const response = await fetch(`${API_BASE_URL}/folders/${folderId}/files`, {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    await handleError("Failed to list files", response);
  }

  return response.json();
}

export async function uploadFile(
  folderId: number,
  file: File,
  token: string
): Promise<DriveFile> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/folders/${folderId}/files`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  if (!response.ok) {
    await handleError("Failed to upload file", response);
  }

  return response.json();
}

export async function downloadFile(fileId: number, token: string): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/files/${fileId}/download`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    await handleError("Failed to download file", response);
  }

  return response.blob();
}

export async function renameFile(
  fileId: number,
  newName: string,
  token: string
): Promise<DriveFile> {
  const response = await fetch(`${API_BASE_URL}/files/${fileId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ name: newName }),
  });

  if (!response.ok) {
    await handleError("Failed to rename file", response);
  }

  return response.json();
}

export async function deleteFile(fileId: number, token: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/files/${fileId}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    await handleError("Failed to delete file", response);
  }
}

// Browse functions
export async function browseDrive(
  parentId: string | undefined,
  token: string
): Promise<{ items: DriveBrowseItem[]; next_page_token?: string }> {
  const params = new URLSearchParams();
  if (parentId) {
    params.append("parent_id", parentId);
  }

  const url = `${API_BASE_URL}/browse${params.toString() ? `?${params.toString()}` : ""}`;
  const response = await fetch(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    await handleError("Failed to browse Drive", response);
  }

  return response.json();
}

// Helper function to format file size
export function formatFileSize(bytes?: number): string {
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

// Helper function to format date
export function formatDate(dateString?: string): string {
  if (!dateString) return "-";
  return new Date(dateString).toLocaleDateString();
}
