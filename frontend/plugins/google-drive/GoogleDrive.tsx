"use client";

import { useCallback, useEffect, useState } from "react";
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
  FolderSync,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
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
  downloadFile,
  deleteFile,
  DriveFolder,
  ConnectionStatus as ConnectionStatusType,
  formatDate,
} from "@/lib/drive";

enum ResourceStatus {
  Ready = "ready",
  Processing = "processing",
  Failed = "failed",
}

interface ResourceRow {
  id: number;
  name: string;
  mimeType: string;
  status: ResourceStatus;
  dateImported: string;
  source: string;
  folderId: number;
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

function StatusChip({ status }: { status: ResourceStatus }) {
  switch (status) {
    case ResourceStatus.Ready:
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-success-50 text-success-700 dark:bg-success-500/10 dark:text-success-400">
          <CheckCircle className="w-3.5 h-3.5" />
          Ready
        </span>
      );
    case ResourceStatus.Processing:
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-warning-50 text-warning-700 dark:bg-warning-500/10 dark:text-warning-400">
          <Clock className="w-3.5 h-3.5" />
          Processing
        </span>
      );
    case ResourceStatus.Failed:
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-error-50 text-error-700 dark:bg-error-500/10 dark:text-error-400">
          <AlertCircle className="w-3.5 h-3.5" />
          Failed
        </span>
      );
  }
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

const ITEMS_PER_PAGE = 10;

function formatMimeType(mimeType?: string): string {
  if (!mimeType) return "FILE";
  const part = mimeType.split("/").pop() || "file";
  if (part.includes("wordprocessingml")) return "DOCX";
  if (part.includes("spreadsheetml")) return "XLSX";
  if (part.includes("presentationml")) return "PPTX";
  return part.toUpperCase();
}

export default function GoogleDrive() {
  const { token } = useAuth();

  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatusType | null>(null);
  const [folders, setFolders] = useState<DriveFolder[]>([]);
  const [resources, setResources] = useState<ResourceRow[]>([]);
  const [totalResources, setTotalResources] = useState(0);
  const [loading, setLoading] = useState(true);
  const [pageLoading, setPageLoading] = useState(false);
  const [showFolderPicker, setShowFolderPicker] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  // Load connection status and folders (once)
  const loadFolders = useCallback(async () => {
    if (!token) {
      setLoading(false);
      return;
    }

    try {
      const status = await getConnectionStatus(token);
      setConnectionStatus(status);

      if (status.connected) {
        const result = await listFolders(token, 0, 100);
        setFolders(result.items);
      }
    } catch (error) {
      console.error("Failed to load folders:", error);
    } finally {
      setLoading(false);
    }
  }, [token]);

  // Load files for the current page across all folders (server-side paginated)
  const loadPage = useCallback(
    async (page: number) => {
      if (!token || folders.length === 0) return;

      setPageLoading(true);
      try {
        const skip = (page - 1) * ITEMS_PER_PAGE;
        // We need to distribute skip/limit across folders.
        // Fetch paginated files from each folder and aggregate.
        // For true server-side pagination, we fetch per-folder with skip/limit.
        // Strategy: fetch all folder totals, then determine which folder(s)
        // the current page spans and fetch only those files.

        let totalCount = 0;
        const folderTotals: { folder: DriveFolder; total: number }[] = [];

        // First pass: get totals for each folder (limit=0 fetch with just total)
        const totalResults = await Promise.all(
          folders.map(async (folder) => {
            const result = await listFiles(folder.id, token, 0, 1);
            return { folder, total: result.total };
          }),
        );

        for (const { folder, total } of totalResults) {
          folderTotals.push({ folder, total });
          totalCount += total;
        }

        setTotalResources(totalCount);

        // Second pass: determine which folders contribute to this page
        const pageResources: ResourceRow[] = [];
        let skipped = 0;
        let remaining = ITEMS_PER_PAGE;

        for (const { folder, total } of folderTotals) {
          if (remaining <= 0) break;

          if (skipped + total <= skip) {
            // This folder is entirely before the current page
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
                dateImported: formatDate(file.last_synced_at || folder.last_synced_at),
                source: "Google Drive",
                folderId: folder.id,
              });
            }
            remaining -= result.items.length;
          }

          skipped += total;
        }

        setResources(pageResources);
      } catch (error) {
        console.error("Failed to load resources:", error);
      } finally {
        setPageLoading(false);
      }
    },
    [token, folders],
  );

  useEffect(() => {
    loadFolders();
  }, [loadFolders]);

  useEffect(() => {
    if (folders.length > 0) {
      loadPage(currentPage);
    }
  }, [folders, currentPage, loadPage]);

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };

  const handleDownload = async (resource: ResourceRow) => {
    if (!token) return;
    setDownloadingId(resource.id);
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
    } catch (error) {
      console.error("Failed to download:", error);
    } finally {
      setDownloadingId(null);
    }
  };

  const handleDelete = async (resource: ResourceRow) => {
    if (!token) return;
    setDeletingId(resource.id);
    try {
      await deleteFile(resource.id, token);
      // Reload the current page from server
      const newTotal = totalResources - 1;
      const maxPage = Math.max(1, Math.ceil(newTotal / ITEMS_PER_PAGE));
      const nextPage = currentPage > maxPage ? maxPage : currentPage;
      setTotalResources(newTotal);
      setCurrentPage(nextPage);
      await loadPage(nextPage);
    } catch (error) {
      console.error("Failed to delete:", error);
    } finally {
      setDeletingId(null);
    }
  };

  const handleReload = () => {
    setCurrentPage(1);
    setFolders([]);
    setResources([]);
    setTotalResources(0);
    setLoading(true);
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
      {/* Header */}
      <div className="bg-card border-b border-border px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-foreground">Resources</h2>
            <p className="text-sm text-muted-foreground">
              All imported files from your connected plugins
            </p>
          </div>
          {connectionStatus?.connected && (
            <Button variant="primary" size="sm" onClick={() => setShowFolderPicker(true)}>
              <FolderSync className="w-4 h-4 mr-2" />
              Sync Folder
            </Button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        <ConnectionStatus status={connectionStatus} onStatusChange={handleReload} />

        {connectionStatus?.connected && totalResources === 0 && !pageLoading ? (
          /* Empty state */
          <div className="rounded-xl border border-border bg-card p-12 text-center">
            <DefaultFileIcon className="mx-auto h-16 w-16 text-muted-foreground/30 mb-4" />
            <h3 className="text-lg font-semibold text-foreground mb-1">No resources yet</h3>
            <p className="text-sm text-muted-foreground">
              Import files from your connected plugins to get started
            </p>
          </div>
        ) : connectionStatus?.connected ? (
          /* Resources table */
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
                    <tr key={resource.id} className="hover:bg-surface-variant/30 transition-colors">
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-3">
                          {getFileIcon(resource.mimeType)}
                          <span className="text-sm font-medium text-foreground">
                            {resource.name}
                          </span>
                        </div>
                      </td>
                      <td className="px-5 py-3">
                        <span className="text-xs text-muted-foreground">
                          {formatMimeType(resource.mimeType)}
                        </span>
                      </td>
                      <td className="px-5 py-3">
                        <StatusChip status={resource.status} />
                      </td>
                      <td className="px-5 py-3">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-surface-variant text-muted-foreground">
                          {resource.source}
                        </span>
                      </td>
                      <td className="px-5 py-3">
                        <span className="text-xs text-muted-foreground">
                          {resource.dateImported}
                        </span>
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-1">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-muted-foreground hover:text-foreground"
                                onClick={() => handleDownload(resource)}
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
                                onClick={() => handleDelete(resource)}
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
                  Showing {startIndex + 1}–{Math.min(startIndex + ITEMS_PER_PAGE, totalResources)}{" "}
                  of {totalResources} resources
                </span>
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    disabled={currentPage === 1 || pageLoading}
                    onClick={() => handlePageChange(currentPage - 1)}
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </Button>
                  {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                    <Button
                      key={page}
                      variant={page === currentPage ? "primary" : "ghost"}
                      size="icon"
                      className="h-8 w-8 text-xs"
                      disabled={pageLoading}
                      onClick={() => handlePageChange(page)}
                    >
                      {page}
                    </Button>
                  ))}
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    disabled={currentPage === totalPages || pageLoading}
                    onClick={() => handlePageChange(currentPage + 1)}
                  >
                    <ChevronRight className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}
          </div>
        ) : null}
      </div>

      {showFolderPicker && (
        <FolderPicker onClose={() => setShowFolderPicker(false)} onFolderSynced={handleReload} />
      )}
    </div>
  );
}
