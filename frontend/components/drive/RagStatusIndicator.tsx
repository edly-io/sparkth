"use client";

import { useState } from "react";
import {
  ragStatusColor,
  ragStatusLabel,
  RAG_STATUS_FALLBACK_COLOR,
  RAG_STATUS_FALLBACK_LABEL,
} from "@/lib/rag-status";

interface RagStatusIndicatorProps {
  fileId: number;
  status: string | null;
  error?: string | null;
}

export function RagStatusIndicator({ fileId, status, error }: RagStatusIndicatorProps) {
  const [hovered, setHovered] = useState(false);
  const color = ragStatusColor[status ?? ""] ?? RAG_STATUS_FALLBACK_COLOR;
  const label = ragStatusLabel[status ?? ""] ?? RAG_STATUS_FALLBACK_LABEL;

  return (
    <div className="relative inline-flex items-center justify-center">
      <span
        data-testid={`rag-status-${fileId}`}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        className={`inline-block w-3 h-3 rounded-full cursor-default ${color}`}
      />
      {hovered && (
        <div
          data-testid={`rag-tooltip-${fileId}`}
          className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 min-w-max rounded-md bg-popover border border-border px-3 py-2 text-xs text-popover-foreground shadow-md"
        >
          <p className="font-medium">{label}</p>
          {error && <p className="mt-1 text-muted-foreground">{error}</p>}
        </div>
      )}
    </div>
  );
}
