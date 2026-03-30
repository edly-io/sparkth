"use client";

import { useState } from "react";
import { Folder, RefreshCw, Trash2 } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { DriveFolder, removeFolder, refreshFolder, formatDate } from "@/lib/drive";
import FolderDetail from "@/components/drive/FolderDetail";

interface FolderListProps {
  folders: DriveFolder[];
  onFoldersChange: () => void;
}

export default function FolderList({ folders, onFoldersChange }: FolderListProps) {
  const { token } = useAuth();
  const [loadingId, setLoadingId] = useState<number | null>(null);
  const [selectedFolder, setSelectedFolder] = useState<DriveFolder | null>(null);

  const handleRefresh = async (folder: DriveFolder) => {
    if (!token) return;

    setLoadingId(folder.id);
    try {
      await refreshFolder(folder.id, token);
      onFoldersChange();
    } catch (error) {
      alert(`Failed to sync: ${error}`);
    } finally {
      setLoadingId(null);
    }
  };

  const handleRemove = async (folder: DriveFolder) => {
    if (!token) return;
    if (
      !confirm(`Remove "${folder.name}" from Sparkth? This won't delete files from Google Drive.`)
    )
      return;

    setLoadingId(folder.id);
    try {
      await removeFolder(folder.id, token);
      onFoldersChange();
    } catch (error) {
      alert(`Failed to remove: ${error}`);
    } finally {
      setLoadingId(null);
    }
  };

  const getSyncStatusStyles = (status: string) => {
    switch (status) {
      case "synced":
        return "text-success-500 bg-success-50 dark:bg-success-500/10";
      case "syncing":
        return "text-secondary-600 bg-secondary-50 dark:bg-secondary-500/10";
      case "error":
        return "text-error-500 bg-error-50 dark:bg-error-500/10";
      default:
        return "text-muted-foreground bg-surface-variant";
    }
  };

  if (folders.length === 0) {
    return (
      <Card variant="outlined" className="py-12 text-center">
        <Folder className="mx-auto h-10 w-10 text-muted-foreground/40 mb-3" />
        <h3 className="text-sm font-medium text-foreground">No folders synced</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Click &quot;Sync Folder&quot; to add a Google Drive folder.
        </p>
      </Card>
    );
  }

  return (
    <>
      <Card variant="outlined" className="p-0 overflow-hidden">
        <ul className="divide-y divide-border">
          {folders.map((folder) => (
            <li
              key={folder.id}
              className="px-5 py-4 hover:bg-surface-variant/50 cursor-pointer transition-colors"
              onClick={() => setSelectedFolder(folder)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Folder className="h-6 w-6 text-warning-500 shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-foreground">{folder.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {folder.file_count} file{folder.file_count !== 1 ? "s" : ""}
                      {folder.last_synced_at &&
                        ` \u2022 Last synced ${formatDate(folder.last_synced_at)}`}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${getSyncStatusStyles(folder.sync_status)}`}
                  >
                    {folder.sync_status}
                  </span>

                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleRefresh(folder)}
                    disabled={loadingId === folder.id}
                    className="h-8 w-8"
                  >
                    <RefreshCw
                      className={`h-4 w-4 ${loadingId === folder.id ? "animate-spin" : ""}`}
                    />
                  </Button>

                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleRemove(folder)}
                    disabled={loadingId === folder.id}
                    className="h-8 w-8 text-muted-foreground hover:text-error-500"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </Card>

      {selectedFolder && (
        <FolderDetail
          folder={selectedFolder}
          onClose={() => setSelectedFolder(null)}
          onFolderChange={onFoldersChange}
        />
      )}
    </>
  );
}
