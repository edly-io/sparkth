"use client";

import { Folder, ChevronRight } from "lucide-react";
import { Spinner } from "@/components/Spinner";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/Dialog";
import { useFolderPicker } from "./useFolderPicker";

interface FolderPickerProps {
  onClose: () => void;
  onFolderSynced: () => void;
}

export default function FolderPicker({ onClose, onFolderSynced }: FolderPickerProps) {
  const {
    items,
    loading,
    error,
    syncingFolderId,
    syncedDriveFolderIds,
    currentPath,
    handleFolderClick,
    handleBreadcrumbClick,
    handleSync,
  } = useFolderPicker({ onClose, onFolderSynced });

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
