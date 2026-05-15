"use client";

import { useCallback, useEffect, useReducer, useRef, useMemo } from "react";
import {
  FileText,
  Image as ImageIcon,
  FileIcon as PdfIcon,
  File as DefaultFileIcon,
  Trash2,
  Download,
  CheckCircle,
  Clock,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  MoreHorizontal,
  RefreshCw,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Spinner } from "@/components/Spinner";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/Button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/Tooltip";
import ConnectionStatus from "@/components/drive/ConnectionStatus";
import FolderPicker from "@/components/drive/FolderPicker";
import {
  getConnectionStatus,
  listFolders,
  listFiles,
  fetchAllPages,
  downloadFile,
  deleteFile,
  refreshFolder,
  getFolderRagStatus,
  DriveFolder,
  ConnectionStatus as ConnectionStatusType,
  formatDate,
  RagStatus,
} from "@/lib/drive";

const ResourceStatus = {
  Ready: "ready",
  Processing: "processing",
  Failed: "failed",
} as const;
type ResourceStatus = (typeof ResourceStatus)[keyof typeof ResourceStatus];

interface ResourceRow {
  id: number;
  name: string;
  mimeType: string;
  status: ResourceStatus;
  ragStatus: RagStatus | null;
  ragError: string | null;
  dateImported: string;
  source: string;
  folderId: number;
}

interface FolderTotal {
  folder: DriveFolder;
  total: number;
}

function getFileIcon(mimeType: string) {
  if (mimeType.includes("pdf")) {
    return <PdfIcon className="w-5 h-5 text-error-500 flex-shrink-0" />;
  }
  if (mimeType.includes("image")) {
    return <ImageIcon className="w-5 h-5 text-pink-500 flex-shrink-0" />;
  }
  if (mimeType.includes("document") || mimeType.includes("word") || mimeType.includes("text")) {
    return <FileText className="w-5 h-5 text-blue-500 flex-shrink-0" />;
  }
  return <DefaultFileIcon className="w-5 h-5 text-muted-foreground flex-shrink-0" />;
}

function mapSyncStatus(syncStatus: string): ResourceStatus {
  switch (syncStatus) {
    case "synced":
      return ResourceStatus.Ready;
    case "syncing":
      return ResourceStatus.Processing;
    case "error":
      return ResourceStatus.Failed;
    default:
      return ResourceStatus.Ready;
  }
}

const CHIP_STYLES = {
  warning: "bg-warning-50 text-warning-700 dark:bg-warning-500/10 dark:text-warning-400",
  error: "bg-error-50 text-error-700 dark:bg-error-500/10 dark:text-error-400",
  success: "bg-success-50 text-success-700 dark:bg-success-500/10 dark:text-success-400",
  muted: "bg-surface-variant text-muted-foreground",
} as const;

function StatusChip({
  tone,
  icon: Icon,
  label,
}: {
  tone: keyof typeof CHIP_STYLES;
  icon: LucideIcon;
  label: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${CHIP_STYLES[tone]}`}
    >
      <Icon className="w-3.5 h-3.5" />
      {label}
    </span>
  );
}

/**
 * Combined sync + RAG status chip. Surfaces the earliest non-final state on
 * the pipeline: Syncing → Sync Failed | Pending → Queued → Indexing → Index Failed | Indexed.
 */
function PipelineStatusChip({
  syncStatus,
  ragStatus,
  ragError,
}: {
  syncStatus: ResourceStatus;
  ragStatus: RagStatus | null;
  ragError: string | null;
}) {
  if (syncStatus === ResourceStatus.Processing) {
    return <StatusChip tone="warning" icon={Clock} label="Syncing" />;
  }
  if (syncStatus === ResourceStatus.Failed) {
    return <StatusChip tone="error" icon={AlertCircle} label="Sync Failed" />;
  }
  // Explicit guard so a future ResourceStatus member can't silently fall through to RAG checks.
  if (syncStatus !== ResourceStatus.Ready) {
    return <StatusChip tone="muted" icon={Clock} label="Unknown" />;
  }
  if (ragStatus === null) {
    return <StatusChip tone="muted" icon={Clock} label="Pending" />;
  }
  if (ragStatus === RagStatus.Queued) {
    return <StatusChip tone="muted" icon={Clock} label="Queued" />;
  }
  if (ragStatus === RagStatus.Processing) {
    return <StatusChip tone="warning" icon={Clock} label="Indexing" />;
  }
  if (ragStatus === RagStatus.Failed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="cursor-default">
            <StatusChip tone="error" icon={AlertCircle} label="Failed" />
          </span>
        </TooltipTrigger>
        <TooltipContent>{ragError ?? "Indexing failed. Try re-syncing the folder."}</TooltipContent>
      </Tooltip>
    );
  }
  if (ragStatus === RagStatus.Ready) {
    return <StatusChip tone="success" icon={CheckCircle} label="Indexed" />;
  }
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs text-muted-foreground">
      —
    </span>
  );
}

const ITEMS_PER_PAGE = 10;
const MAX_VISIBLE_PAGES = 5;

function formatMimeType(mimeType?: string): string {
  if (!mimeType) return "FILE";
  const part = mimeType.split("/").pop() || "file";
  if (part.includes("wordprocessingml")) return "DOCX";
  if (part.includes("spreadsheetml")) return "XLSX";
  if (part.includes("presentationml")) return "PPTX";
  return part.toUpperCase();
}

/** Build a windowed list of page numbers with distinct ellipsis markers. */
function getPageNumbers(
  current: number,
  total: number,
): (number | "ellipsis-start" | "ellipsis-end")[] {
  if (total <= MAX_VISIBLE_PAGES) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const pages: (number | "ellipsis-start" | "ellipsis-end")[] = [1];
  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);

  if (start > 2) pages.push("ellipsis-start");
  for (let i = start; i <= end; i++) pages.push(i);
  if (end < total - 1) pages.push("ellipsis-end");
  pages.push(total);

  return pages;
}

/* ------------------------------------------------------------------ */
/*  State management via useReducer                                    */
/* ------------------------------------------------------------------ */

interface DriveState {
  connectionStatus: ConnectionStatusType | null;
  folders: DriveFolder[];
  resources: ResourceRow[];
  totalResources: number;
  loading: boolean;
  pageLoading: boolean;
  totalsLoading: boolean;
  error: string | null;
  showFolderPicker: boolean;
  deletingId: number | null;
  downloadingId: number | null;
  resyncing: boolean;
  currentPage: number;
}

type DriveAction =
  | { type: "SET_CONNECTION_STATUS"; payload: ConnectionStatusType | null }
  | { type: "SET_FOLDERS"; payload: DriveFolder[] }
  | { type: "SET_RESOURCES"; payload: ResourceRow[] }
  | { type: "SET_TOTAL_RESOURCES"; payload: number }
  | { type: "SET_LOADING"; payload: boolean }
  | { type: "SET_PAGE_LOADING"; payload: boolean }
  | { type: "SET_TOTALS_LOADING"; payload: boolean }
  | { type: "SET_ERROR"; payload: string | null }
  | { type: "SET_SHOW_FOLDER_PICKER"; payload: boolean }
  | { type: "SET_DELETING_ID"; payload: number | null }
  | { type: "SET_DOWNLOADING_ID"; payload: number | null }
  | { type: "SET_RESYNCING"; payload: boolean }
  | { type: "SET_CURRENT_PAGE"; payload: number }
  | {
      type: "UPDATE_RAG_STATUSES";
      payload: Record<number, { status: RagStatus | null; error: string | null }>;
    }
  | { type: "RELOAD" };

const initialDriveState: DriveState = {
  connectionStatus: null,
  folders: [],
  resources: [],
  totalResources: 0,
  loading: true,
  pageLoading: false,
  totalsLoading: false,
  error: null,
  showFolderPicker: false,
  deletingId: null,
  downloadingId: null,
  resyncing: false,
  currentPage: 1,
};

function driveReducer(state: DriveState, action: DriveAction): DriveState {
  switch (action.type) {
    case "SET_CONNECTION_STATUS":
      return { ...state, connectionStatus: action.payload };
    case "SET_FOLDERS":
      return { ...state, folders: action.payload };
    case "SET_RESOURCES":
      return { ...state, resources: action.payload };
    case "SET_TOTAL_RESOURCES":
      return { ...state, totalResources: action.payload };
    case "SET_LOADING":
      return { ...state, loading: action.payload };
    case "SET_PAGE_LOADING":
      return { ...state, pageLoading: action.payload };
    case "SET_TOTALS_LOADING":
      return { ...state, totalsLoading: action.payload };
    case "SET_ERROR":
      return { ...state, error: action.payload };
    case "SET_SHOW_FOLDER_PICKER":
      return { ...state, showFolderPicker: action.payload };
    case "SET_DELETING_ID":
      return { ...state, deletingId: action.payload };
    case "SET_DOWNLOADING_ID":
      return { ...state, downloadingId: action.payload };
    case "SET_RESYNCING":
      return { ...state, resyncing: action.payload };
    case "SET_CURRENT_PAGE":
      return { ...state, currentPage: action.payload };
    case "UPDATE_RAG_STATUSES":
      return {
        ...state,
        resources: state.resources.map((r) =>
          r.id in action.payload
            ? { ...r, ragStatus: action.payload[r.id].status, ragError: action.payload[r.id].error }
            : r,
        ),
      };
    case "RELOAD":
      return {
        ...state,
        currentPage: 1,
        folders: [],
        resources: [],
        totalResources: 0,
        error: null,
        loading: true,
      };
  }
}

/* ------------------------------------------------------------------ */
/*  Extracted sub-components                                           */
/* ------------------------------------------------------------------ */

function ResourcesHeader() {
  return (
    <div className="bg-card border-b border-border px-6 py-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-foreground">Resources</h2>
          <p className="text-sm text-muted-foreground">
            All imported files from your connected plugins
          </p>
        </div>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-xl border border-border bg-card p-12 text-center">
      <DefaultFileIcon className="mx-auto h-16 w-16 text-muted-foreground/30 mb-4" />
      <h3 className="text-lg font-semibold text-foreground mb-1">No resources yet</h3>
      <p className="text-sm text-muted-foreground">
        Import files from your connected plugins to get started
      </p>
    </div>
  );
}

interface ResourcesTableProps {
  resources: ResourceRow[];
  pageLoading: boolean;
  currentPage: number;
  totalPages: number;
  totalResources: number;
  startIndex: number;
  downloadingId: number | null;
  deletingId: number | null;
  onDownload: (resource: ResourceRow) => void;
  onDelete: (resource: ResourceRow) => void;
  onPageChange: (page: number) => void;
}

function ResourcesTable({
  resources,
  pageLoading,
  currentPage,
  totalPages,
  totalResources,
  startIndex,
  downloadingId,
  deletingId,
  onDownload,
  onDelete,
  onPageChange,
}: ResourcesTableProps) {
  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="bg-surface-variant/50">
            <th className="text-left px-5 py-3 text-xs font-semibold text-muted-foreground">
              File Name
            </th>
            <th className="text-left px-5 py-3 text-xs font-semibold text-muted-foreground">
              Type
            </th>
            <th className="text-left px-5 py-3 text-xs font-semibold text-muted-foreground">
              Status
            </th>
            <th className="text-left px-5 py-3 text-xs font-semibold text-muted-foreground">
              Source
            </th>
            <th className="text-left px-5 py-3 text-xs font-semibold text-muted-foreground">
              Date Imported
            </th>
            <th className="text-left px-5 py-3 text-xs font-semibold text-muted-foreground w-24">
              Actions
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {pageLoading ? (
            <tr>
              <td colSpan={6} className="py-12 text-center">
                <Spinner className="mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">Loading resources...</p>
              </td>
            </tr>
          ) : (
            resources.map((resource) => (
              <tr
                key={`${resource.folderId}-${resource.id}`}
                className="hover:bg-surface-variant/30 transition-colors"
              >
                <td className="px-5 py-3">
                  <div className="flex items-center gap-3">
                    {getFileIcon(resource.mimeType)}
                    <span className="text-sm font-medium text-foreground">{resource.name}</span>
                  </div>
                </td>
                <td className="px-5 py-3">
                  <span className="text-xs text-muted-foreground">
                    {formatMimeType(resource.mimeType)}
                  </span>
                </td>
                <td className="px-5 py-3">
                  <PipelineStatusChip
                    syncStatus={resource.status}
                    ragStatus={resource.ragStatus}
                    ragError={resource.ragError}
                  />
                </td>
                <td className="px-5 py-3">
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-surface-variant text-muted-foreground">
                    {resource.source}
                  </span>
                </td>
                <td className="px-5 py-3">
                  <span className="text-xs text-muted-foreground">{resource.dateImported}</span>
                </td>
                <td className="px-5 py-3">
                  <div className="flex items-center gap-1">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-muted-foreground hover:text-foreground"
                          onClick={() => onDownload(resource)}
                          disabled={downloadingId === resource.id}
                        >
                          <Download className="w-4 h-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Download</TooltipContent>
                    </Tooltip>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-muted-foreground hover:text-error-500 hover:bg-error-50 dark:hover:bg-error-900/30"
                          onClick={() => onDelete(resource)}
                          disabled={deletingId === resource.id}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Delete</TooltipContent>
                    </Tooltip>
                  </div>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-5 py-3 border-t border-border">
          <span className="text-xs text-muted-foreground">
            Showing {startIndex + 1}–{Math.min(startIndex + ITEMS_PER_PAGE, totalResources)} of{" "}
            {totalResources} resources
          </span>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              disabled={currentPage === 1 || pageLoading}
              onClick={() => onPageChange(currentPage - 1)}
            >
              <ChevronLeft className="w-4 h-4" />
            </Button>
            {getPageNumbers(currentPage, totalPages).map((page) =>
              page === "ellipsis-start" || page === "ellipsis-end" ? (
                <span key={page} className="w-8 h-8 flex items-center justify-center">
                  <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
                </span>
              ) : (
                <Button
                  key={page}
                  variant={page === currentPage ? "primary" : "ghost"}
                  size="icon"
                  className="h-8 w-8 text-xs"
                  disabled={pageLoading}
                  onClick={() => onPageChange(page)}
                >
                  {page}
                </Button>
              ),
            )}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              disabled={currentPage === totalPages || pageLoading}
              onClick={() => onPageChange(currentPage + 1)}
            >
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main component                                                     */
/* ------------------------------------------------------------------ */

export default function GoogleDrive() {
  const { token } = useAuth();
  const [state, dispatch] = useReducer(driveReducer, initialDriveState);

  const {
    connectionStatus,
    folders,
    resources,
    totalResources,
    loading,
    pageLoading,
    totalsLoading,
    error,
    showFolderPicker,
    deletingId,
    downloadingId,
    resyncing,
    currentPage,
  } = state;

  // Cache folder totals to avoid N+1 requests on every page change
  const folderTotalsRef = useRef<FolderTotal[]>([]);

  // Load connection status and all folders (paginated fetch)
  const loadFolders = useCallback(async () => {
    if (!token) {
      dispatch({ type: "SET_LOADING", payload: false });
      return;
    }

    dispatch({ type: "SET_ERROR", payload: null });
    try {
      const status = await getConnectionStatus(token);
      dispatch({ type: "SET_CONNECTION_STATUS", payload: status });

      if (status.connected) {
        const allFolders = await fetchAllPages((skip, limit) => listFolders(token, skip, limit));
        dispatch({ type: "SET_FOLDERS", payload: allFolders });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load resources";
      dispatch({ type: "SET_ERROR", payload: message });
      console.error("Failed to load folders:", err);
    } finally {
      dispatch({ type: "SET_LOADING", payload: false });
    }
  }, [token]);

  // Fetch folder totals once, cache in ref
  const loadFolderTotals = useCallback(async () => {
    if (!token || folders.length === 0) return;

    dispatch({ type: "SET_TOTALS_LOADING", payload: true });
    try {
      const results = await Promise.all(
        folders.map(async (folder) => {
          const result = await listFiles(folder.id, token, 0, 1);
          return { folder, total: result.total };
        }),
      );

      folderTotalsRef.current = results;
      dispatch({
        type: "SET_TOTAL_RESOURCES",
        payload: results.reduce((sum, r) => sum + r.total, 0),
      });
      dispatch({ type: "SET_ERROR", payload: null });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load file counts";
      dispatch({ type: "SET_ERROR", payload: message });
      console.error("Failed to load folder totals:", err);
    } finally {
      dispatch({ type: "SET_TOTALS_LOADING", payload: false });
    }
  }, [token, folders]);

  // Load files for the current page using cached folder totals
  const loadPage = useCallback(
    async (page: number) => {
      if (!token || folderTotalsRef.current.length === 0) return;

      dispatch({ type: "SET_PAGE_LOADING", payload: true });
      try {
        const skip = (page - 1) * ITEMS_PER_PAGE;
        const pageResources: ResourceRow[] = [];
        let skipped = 0;
        let remaining = ITEMS_PER_PAGE;

        for (const { folder, total } of folderTotalsRef.current) {
          if (remaining <= 0) break;

          if (skipped + total <= skip) {
            skipped += total;
            continue;
          }

          const folderSkip = Math.max(0, skip - skipped);
          const folderLimit = Math.min(remaining, total - folderSkip);

          if (folderLimit > 0) {
            const result = await listFiles(folder.id, token, folderSkip, folderLimit);
            for (const file of result.items) {
              pageResources.push({
                id: file.id,
                name: file.name,
                mimeType: file.mime_type || "",
                status: mapSyncStatus(folder.sync_status),
                ragStatus: file.rag_status ?? null,
                ragError: file.rag_error ?? null,
                dateImported: formatDate(file.last_synced_at || folder.last_synced_at),
                source: "Google Drive",
                folderId: folder.id,
              });
            }
            remaining -= result.items.length;
          }

          skipped += total;
        }

        dispatch({ type: "SET_RESOURCES", payload: pageResources });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to load resources";
        dispatch({ type: "SET_ERROR", payload: message });
        console.error("Failed to load resources:", err);
      } finally {
        dispatch({ type: "SET_PAGE_LOADING", payload: false });
      }
    },
    [token],
  );

  useEffect(() => {
    loadFolders();
  }, [loadFolders]);

  // When folders change, fetch totals once
  useEffect(() => {
    if (folders.length > 0) {
      loadFolderTotals();
    }
  }, [folders, loadFolderTotals]);

  // When totals are ready or page changes, load the page
  useEffect(() => {
    if (totalResources > 0) {
      loadPage(currentPage);
    }
  }, [currentPage, totalResources, loadPage]);

  // Poll RAG statuses for files that are still queued or processing
  const folderIdsWithNonTerminal = useMemo(() => {
    const nonTerminalStatuses = new Set<string>(["queued", "processing"]);
    const ids = new Set<number>();
    for (const r of resources) {
      if (r.ragStatus && nonTerminalStatuses.has(r.ragStatus)) {
        ids.add(r.folderId);
      }
    }
    return Array.from(ids);
  }, [resources]);

  useEffect(() => {
    if (!token || folderIdsWithNonTerminal.length === 0) return;

    const BASE_DELAY = 5_000;
    const MAX_DELAY = 30_000;
    let cancelled = false;
    let retryDelay = BASE_DELAY;
    let timerId: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      try {
        const results = await Promise.all(
          folderIdsWithNonTerminal.map((folderId) => getFolderRagStatus(folderId, token)),
        );
        if (cancelled) return;

        const statusMap: Record<number, { status: RagStatus | null; error: string | null }> = {};
        for (const folder of results) {
          for (const f of folder.files) {
            statusMap[f.file_id] = { status: f.rag_status, error: f.rag_error };
          }
        }
        dispatch({ type: "UPDATE_RAG_STATUSES", payload: statusMap });

        retryDelay = BASE_DELAY;
        if (!cancelled) timerId = setTimeout(poll, BASE_DELAY);
      } catch (err) {
        console.warn("RAG status poll failed, retrying in", retryDelay, "ms:", err);
        if (!cancelled) {
          timerId = setTimeout(poll, retryDelay);
          retryDelay = Math.min(retryDelay * 2, MAX_DELAY);
        }
      }
    };

    timerId = setTimeout(poll, BASE_DELAY);
    return () => {
      cancelled = true;
      if (timerId) clearTimeout(timerId);
    };
  }, [token, folderIdsWithNonTerminal]);

  const handleDownload = async (resource: ResourceRow) => {
    if (!token) return;
    dispatch({ type: "SET_DOWNLOADING_ID", payload: resource.id });
    try {
      const blob = await downloadFile(resource.id, token);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = resource.name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to download file";
      dispatch({ type: "SET_ERROR", payload: message });
      console.error("Failed to download:", err);
    } finally {
      dispatch({ type: "SET_DOWNLOADING_ID", payload: null });
    }
  };

  const handleDelete = async (resource: ResourceRow) => {
    if (!token) return;
    if (!confirm(`Remove "${resource.name}" from Sparkth? The file will remain in Google Drive.`))
      return;

    dispatch({ type: "SET_DELETING_ID", payload: resource.id });
    try {
      await deleteFile(resource.id, token);
      // Refresh totals cache and adjust page
      await loadFolderTotals();
      const newTotal = folderTotalsRef.current.reduce((sum, r) => sum + r.total, 0);
      const maxPage = Math.max(1, Math.ceil(newTotal / ITEMS_PER_PAGE));
      if (currentPage > maxPage) {
        dispatch({ type: "SET_CURRENT_PAGE", payload: maxPage });
      }
      // useEffect on totalResources/currentPage will trigger loadPage
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to delete file";
      dispatch({ type: "SET_ERROR", payload: message });
      console.error("Failed to delete:", err);
    } finally {
      dispatch({ type: "SET_DELETING_ID", payload: null });
    }
  };

  const handleResync = async () => {
    if (!token || folders.length === 0) return;

    dispatch({ type: "SET_RESYNCING", payload: true });
    dispatch({ type: "SET_ERROR", payload: null });
    try {
      const results = await Promise.allSettled(
        folders.map((folder) => refreshFolder(folder.id, token)),
      );
      const failures = results.filter((r) => r.status === "rejected");
      if (failures.length > 0) {
        dispatch({
          type: "SET_ERROR",
          payload: `Re-sync failed for ${failures.length} of ${folders.length} folder(s)`,
        });
      }
      handleReload();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to re-sync folders";
      dispatch({ type: "SET_ERROR", payload: message });
      console.error("Failed to re-sync:", err);
    } finally {
      dispatch({ type: "SET_RESYNCING", payload: false });
    }
  };

  const handleReload = () => {
    dispatch({ type: "RELOAD" });
    folderTotalsRef.current = [];
    loadFolders();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <Spinner className="mx-auto mb-4" />
          <p className="text-sm text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  const totalPages = Math.ceil(totalResources / ITEMS_PER_PAGE);
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;

  return (
    <div className="flex flex-col h-full bg-surface-variant/30">
      <ResourcesHeader />

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        <ConnectionStatus
          status={connectionStatus}
          onStatusChange={handleReload}
          onSyncFolder={() => dispatch({ type: "SET_SHOW_FOLDER_PICKER", payload: true })}
          onResync={handleResync}
          resyncing={resyncing}
        />

        {error && (
          <div className="flex items-center justify-between rounded-lg border border-error-200 bg-error-50 dark:border-error-800 dark:bg-error-900/30 px-4 py-3">
            <p className="text-sm text-error-700 dark:text-error-400">{error}</p>
            <Button variant="ghost" size="sm" onClick={handleReload}>
              <RefreshCw className="w-4 h-4 mr-1" />
              Retry
            </Button>
          </div>
        )}

        {connectionStatus?.connected &&
        totalResources === 0 &&
        !pageLoading &&
        !totalsLoading &&
        !error ? (
          <EmptyState />
        ) : connectionStatus?.connected ? (
          <ResourcesTable
            resources={resources}
            pageLoading={pageLoading}
            currentPage={currentPage}
            totalPages={totalPages}
            totalResources={totalResources}
            startIndex={startIndex}
            downloadingId={downloadingId}
            deletingId={deletingId}
            onDownload={handleDownload}
            onDelete={handleDelete}
            onPageChange={(page) => dispatch({ type: "SET_CURRENT_PAGE", payload: page })}
          />
        ) : null}
      </div>

      {showFolderPicker && (
        <FolderPicker
          onClose={() => dispatch({ type: "SET_SHOW_FOLDER_PICKER", payload: false })}
          onFolderSynced={handleReload}
        />
      )}
    </div>
  );
}
