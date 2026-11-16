import { useCallback, useEffect, useState } from "react";
import { getFolderDocumentStatus } from "@/plugins/googledrive/src/client";
import { DocumentStatus } from "@/plugins/googledrive/src/types";

/** Each file's processing status and error, keyed by file id. */
export type DocumentStatusMap = Record<
  number,
  { status: DocumentStatus | null; error: string | null }
>;

/** What `useDocumentStatusPolling` returns. */
export interface DocumentStatusPollingResult {
  documentStatuses: DocumentStatusMap;
  /** Starts polling again, for example after a folder is refreshed. */
  restart: () => void;
}

const BASE_DELAY = 5000;
const MAX_DELAY = 30000;

/**
 * Polls the document status of every file in the folders `folderIds`, until each file is ready,
 * failed or has no status. Polls every 5 seconds, doubling the wait after a failed poll up to 30
 * seconds.
 */
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
