import { useCallback, useEffect, useState } from "react";
import { getFolderRagStatus, RagStatus } from "./drive";

export type RagStatusMap = Record<number, { status: RagStatus | null; error: string | null }>;

export interface RagStatusPollingResult {
  ragStatuses: RagStatusMap;
  restart: () => void;
}

const BASE_DELAY = 5000;
const MAX_DELAY = 30000;

export function useRagStatusPolling(
  folderIds: number[],
  token: string | null,
): RagStatusPollingResult {
  const [ragStatuses, setRagStatuses] = useState<RagStatusMap>({});
  const [pollKey, setPollKey] = useState(0);

  const restart = useCallback(() => {
    setPollKey((k) => k + 1);
  }, []);

  const folderIdsKey = folderIds
    .slice()
    .sort((a, b) => a - b)
    .join(",");

  useEffect(() => {
    if (!folderIdsKey || !token) return;

    setRagStatuses({});

    let cancelled = false;
    let allTerminal = false;
    let timerId: ReturnType<typeof setTimeout> | undefined;
    let delay = BASE_DELAY;

    const fetchStatuses = async (): Promise<boolean> => {
      const ids = folderIdsKey.split(",").map(Number);
      try {
        const results = await Promise.all(ids.map((id) => getFolderRagStatus(id, token!)));
        if (!cancelled) {
          const map: RagStatusMap = {};
          for (const data of results) {
            for (const f of data.files) {
              map[f.file_id] = { status: f.rag_status, error: f.rag_error };
            }
          }
          setRagStatuses(map);

          const allFiles = results.flatMap((r) => r.files);
          allTerminal = allFiles.every(
            (f) =>
              f.rag_status === RagStatus.Ready ||
              f.rag_status === RagStatus.Failed ||
              f.rag_status === null,
          );
          delay = BASE_DELAY;
        }
        return true;
      } catch {
        if (!cancelled) {
          delay = Math.min(delay * 2, MAX_DELAY);
        }
        return false;
      }
    };

    const poll = async () => {
      await fetchStatuses();
      if (!cancelled && !allTerminal) {
        timerId = setTimeout(poll, delay);
      }
    };

    poll();

    return () => {
      cancelled = true;
      if (timerId) clearTimeout(timerId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [folderIdsKey, token, pollKey]);

  return { ragStatuses, restart };
}
