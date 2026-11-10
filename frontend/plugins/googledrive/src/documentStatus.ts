/** The badge color for each document status. */
export const documentStatusColor: Record<string, string> = {
  queued: "bg-gray-300",
  ready: "bg-green-500",
  processing: "bg-yellow-500",
  failed: "bg-red-500",
};

/** The badge label for each document status. */
export const documentStatusLabel: Record<string, string> = {
  queued: "Queued",
  ready: "Ready",
  processing: "Processing",
  failed: "Failed",
};

/** The badge color for a status with no entry in `documentStatusColor`, or none yet. */
export const DOCUMENT_STATUS_FALLBACK_COLOR = "bg-gray-300";
/** The badge label for a status with no entry in `documentStatusLabel`, or none yet. */
export const DOCUMENT_STATUS_FALLBACK_LABEL = "Queued";
