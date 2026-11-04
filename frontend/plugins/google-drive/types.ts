import type { Schema } from "@/lib/api";

export type ConnectionStatus = Schema<"GoogleDriveConnectionStatusResponse">;
export type DriveFolder = Schema<"DriveFolderResponse">;
export type DriveFile = Schema<"DriveFileResponse">;
export type DriveBrowseItem = Schema<"DriveBrowseItem">;
export type DriveBrowseResponse = Schema<"DriveBrowseResponse">;
export type SyncStatus = Schema<"SyncStatusResponse">;
export type FolderRagStatusResponse = Schema<"FolderRagStatusResponse">;

// openapi-typescript emits one monomorphic paginated schema per item type,
// so each page shape is aliased directly (like every other type above) rather
// than reconstructed as a hand-written generic that could drift.
export type PaginatedFolders = Schema<"PaginatedResponse_DriveFolderResponse_">;
export type PaginatedFiles = Schema<"PaginatedResponse_DriveFileResponse_">;

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
