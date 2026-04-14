import { useCallback, useEffect, useState } from "react";
import { getFolderRagStatus, RagStatus } from "./drive";

export type RagStatusMap = Record<number, { status: RagStatus | null; error: string | null }>;

export interface RagStatusPollingResult {
  ragStatuses: RagStatusMap;
  restart: () => void;
}

export function useRagStatusPolling(
  folderId: number | null,
  token: string | null,
): RagStatusPollingResult {
  const [ragStatuses, setRagStatuses] = useState<RagStatusMap>({});
  const [pollKey, setPollKey] = useState(0);

  const restart = useCallback(() => {
    setPollKey((k) => k + 1);
  }, []);

  useEffect(() => {
    if (!folderId || !token) return;

    setRagStatuses({});

    let cancelled = false;
    let allTerminal = false;
    let timerId: ReturnType<typeof setTimeout> | undefined;

    const fetchStatuses = async () => {
      try {
        const data = await getFolderRagStatus(folderId, token);
        if (!cancelled) {
          const map: RagStatusMap = {};
          for (const f of data.files) {
            map[f.file_id] = { status: f.rag_status, error: f.rag_error };
          }
          setRagStatuses(map);
          allTerminal =
            data.files.length === 0 ||
            data.files.every(
              (f) => f.rag_status === "ready" || f.rag_status === "failed" || f.rag_status === null,
            );
        }
      } catch {
        // silently ignore polling errors
      }
    };

    const poll = async () => {
      await fetchStatuses();
      if (!cancelled && !allTerminal) {
        timerId = setTimeout(poll, 5000);
      }
    };

    poll();

    return () => {
      cancelled = true;
      if (timerId) clearTimeout(timerId);
    };
  }, [folderId, token, pollKey]);

  return { ragStatuses, restart };
}
