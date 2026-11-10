import type { Schema } from "@/lib/api";

/** Whether the user's Google account is connected, as the OAuth status endpoint returns it. */
export type ConnectionStatus = Schema<"GoogleDriveConnectionStatusResponse">;
/** The Google consent URL that starts connecting a Google account. */
export type AuthorizationUrlResponse = Schema<"GoogleDriveAuthorizationUrlResponse">;
/** A Drive folder the user synced. */
export type DriveFolder = Schema<"DriveFolderResponse">;
/** A file in a synced folder. */
export type DriveFile = Schema<"DriveFileResponse">;
/** A folder or file in the user's Drive, listed while choosing a folder to sync. */
export type DriveBrowseItem = Schema<"DriveBrowseItem">;
/** One level of the user's Drive, listed while choosing a folder to sync. */
export type DriveBrowseResponse = Schema<"DriveBrowseResponse">;
/** The result of refreshing a synced folder. */
export type SyncStatus = Schema<"SyncStatusResponse">;
/** The processing status of each file in a synced folder. */
export type FolderDocumentStatusResponse = Schema<"FolderRagStatusResponse">;

// openapi-typescript emits one monomorphic paginated schema per item type,
// so each page shape is aliased directly (like every other type above) rather
// than reconstructed as a hand-written generic that could drift.
/** A page of synced folders. */
export type PaginatedFolders = Schema<"PaginatedResponse_DriveFolderResponse_">;
/** A page of a synced folder's files. */
export type PaginatedFiles = Schema<"PaginatedResponse_DriveFileResponse_">;

/**
 * A document's processing status, as values. The generated client only emits types (erased at
 * runtime), so the values live here; `satisfies` checks them against the generated union, so any
 * backend enum change fails the type check after regeneration.
 */
export const DocumentStatus = {
  Queued: "queued",
  Processing: "processing",
  Ready: "ready",
  Failed: "failed",
} as const satisfies Record<string, Schema<"DocumentStatus">>;
export type DocumentStatus = Schema<"DocumentStatus">;
