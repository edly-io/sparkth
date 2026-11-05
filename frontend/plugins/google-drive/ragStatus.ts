export const ragStatusColor: Record<string, string> = {
  queued: "bg-gray-300",
  ready: "bg-green-500",
  processing: "bg-yellow-500",
  failed: "bg-red-500",
};

export const ragStatusLabel: Record<string, string> = {
  queued: "Queued",
  ready: "Ready",
  processing: "Processing",
  failed: "Failed",
};

export const RAG_STATUS_FALLBACK_COLOR = "bg-gray-300";
export const RAG_STATUS_FALLBACK_LABEL = "Queued";
