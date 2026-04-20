"use client";

import { useCallback, useEffect, useState } from "react";
import { Folder, ChevronRight } from "lucide-react";
import { Spinner } from "@/components/Spinner";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/Dialog";
import { browseDrive, syncFolder, listFolders, fetchAllPages, DriveBrowseItem } from "@/lib/drive";

interface FolderPickerProps {
  onClose: () => void;
  onFolderSynced: () => void;
}

interface BreadcrumbItem {
  id: string | undefined;
  name: string;
}

export default function FolderPicker({ onClose, onFolderSynced }: FolderPickerProps) {
  const { token } = useAuth();
  const [items, setItems] = useState<DriveBrowseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncingFolderId, setSyncingFolderId] = useState<string | null>(null);
  const [syncedDriveFolderIds, setSyncedDriveFolderIds] = useState<Set<string>>(new Set());
  const [currentPath, setCurrentPath] = useState<BreadcrumbItem[]>([
    { id: undefined, name: "My Drive" },
  ]);

  const currentFolderId = currentPath[currentPath.length - 1].id;

  // Load already-synced folder IDs once on mount
  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const allFolders = await fetchAllPages((skip, limit) => listFolders(token, skip, limit));
        setSyncedDriveFolderIds(new Set(allFolders.map((f) => f.drive_folder_id)));
      } catch (err) {
        console.error("Failed to load synced folders:", err);
      }
    })();
  }, [token]);

  const loadItems = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    try {
      const result = await browseDrive(currentFolderId, token);
      const folders = result.items.filter((item) => item.is_folder);
      setItems(folders);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to browse Drive";
      setError(message);
      console.error("Failed to browse Drive:", err);
    } finally {
      setLoading(false);
    }
  }, [token, currentFolderId]);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  const handleFolderClick = (item: DriveBrowseItem) => {
    setCurrentPath([...currentPath, { id: item.id, name: item.name }]);
  };

  const handleBreadcrumbClick = (index: number) => {
    setCurrentPath(currentPath.slice(0, index + 1));
  };

  const handleSync = async (item: DriveBrowseItem) => {
    if (!token) return;

    setSyncingFolderId(item.id);
    try {
      await syncFolder(item.id, token);
      onFolderSynced();
      onClose();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      if (message.includes("already synced")) {
        setSyncedDriveFolderIds((prev) => new Set(prev).add(item.id));
      } else {
        alert(`Failed to sync folder: ${message}`);
      }
    } finally {
      setSyncingFolderId(null);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Select a folder to sync</DialogTitle>
          <DialogDescription>
            Browse your Google Drive and pick a folder to sync with Sparkth.
          </DialogDescription>
        </DialogHeader>

        {error && <p className="text-sm text-error-600 dark:text-error-400">{error}</p>}

        <nav className="flex" aria-label="Breadcrumb">
          <ol className="flex items-center gap-1 text-sm">
            {currentPath.map((item, index) => (
              <li key={item.id ?? "root"} className="flex items-center">
                {index > 0 && <ChevronRight className="h-3.5 w-3.5 text-muted-foreground mx-0.5" />}
                <button
                  onClick={() => handleBreadcrumbClick(index)}
                  className={
                    index === currentPath.length - 1
                      ? "text-foreground font-medium"
                      : "text-primary-600 hover:text-primary-700 dark:text-primary-400"
                  }
                >
                  {item.name}
                </button>
              </li>
            ))}
          </ol>
        </nav>

        <div className="flex-1 overflow-y-auto -mx-4 sm:-mx-6 px-4 sm:px-6 min-h-[200px]">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Spinner size="md" />
            </div>
          ) : items.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground text-sm">
              No folders found in this location
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {items.map((item) => (
                <li
                  key={item.id}
                  className="flex items-center justify-between py-3 hover:bg-surface-variant/50 -mx-2 px-2 rounded-lg transition-colors cursor-pointer"
                >
                  <button
                    onClick={() => handleFolderClick(item)}
                    className="flex items-center gap-3 flex-1 text-left cursor-pointer"
                  >
                    <Folder className="h-5 w-5 text-warning-500 shrink-0" />
                    <span className="text-sm text-foreground">{item.name}</span>
                  </button>
                  {syncedDriveFolderIds.has(item.id) ? (
                    <span className="text-xs text-muted-foreground px-2">Synced</span>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleSync(item)}
                      disabled={syncingFolderId !== null}
                      loading={syncingFolderId === item.id}
                    >
                      Sync
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
