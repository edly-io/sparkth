import { useCallback, useEffect, useState } from "react";
import { getFolderDocumentStatus } from "@/plugins/google-drive/client";
import { DocumentStatus } from "@/plugins/google-drive/types";

export type DocumentStatusMap = Record<
  number,
  { status: DocumentStatus | null; error: string | null }
>;

export interface DocumentStatusPollingResult {
  documentStatuses: DocumentStatusMap;
  restart: () => void;
}

const BASE_DELAY = 5000;
const MAX_DELAY = 30000;

export function useDocumentStatusPolling(
  folderIds: number[],
  token: string | null,
): DocumentStatusPollingResult {
  const [documentStatuses, setDocumentStatuses] = useState<DocumentStatusMap>({});
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

    setDocumentStatuses({});

    let cancelled = false;
    let allTerminal = false;
    let timerId: ReturnType<typeof setTimeout> | undefined;
    let delay = BASE_DELAY;

    const fetchStatuses = async (): Promise<boolean> => {
      const ids = folderIdsKey.split(",").map(Number);
      try {
        const results = await Promise.all(ids.map((id) => getFolderDocumentStatus(id, token!)));
        if (!cancelled) {
          const map: DocumentStatusMap = {};
          for (const data of results) {
            for (const f of data.files) {
              map[f.file_id] = { status: f.rag_status ?? null, error: f.rag_error ?? null };
            }
          }
          setDocumentStatuses(map);

          const allFiles = results.flatMap((r) => r.files);
          allTerminal = allFiles.every(
            (f) =>
              f.rag_status === DocumentStatus.Ready ||
              f.rag_status === DocumentStatus.Failed ||
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

  return { documentStatuses, restart };
}
