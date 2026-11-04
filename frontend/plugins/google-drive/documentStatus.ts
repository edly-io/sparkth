export const documentStatusColor: Record<string, string> = {
  queued: "bg-gray-300",
  ready: "bg-green-500",
  processing: "bg-yellow-500",
  failed: "bg-red-500",
};

export const documentStatusLabel: Record<string, string> = {
  queued: "Queued",
  ready: "Ready",
  processing: "Processing",
  failed: "Failed",
};

export const DOCUMENT_STATUS_FALLBACK_COLOR = "bg-gray-300";
export const DOCUMENT_STATUS_FALLBACK_LABEL = "Queued";
