"use client";

import { useCallback, useEffect, useState } from "react";
import { Folder, FileText, ChevronRight } from "lucide-react";
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
import { listFolders, listFiles, fetchAllPages, DriveFolder, DriveFile } from "@/lib/drive";
import { useRagStatusPolling } from "@/lib/useRagStatusPolling";
import { RagStatusIndicator } from "./RagStatusIndicator";
import GoogleDriveIcon from "@/plugins/google-drive/GoogleDriveIcon";

export interface SelectedDriveFile {
  id: number;
  name: string;
  mime_type?: string;
  size?: number;
}

interface DriveFilePickerProps {
  onClose: () => void;
  onFileSelected: (files: SelectedDriveFile[]) => void;
  selectedFileIds?: number[];
}

export default function DriveFilePicker({
  onClose,
  onFileSelected,
  selectedFileIds: initialSelectedIds,
}: DriveFilePickerProps) {
  const { token } = useAuth();
  const [folders, setFolders] = useState<DriveFolder[]>([]);
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<DriveFolder | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedFileIds, setSelectedFileIds] = useState<Set<number>>(
    () => new Set(initialSelectedIds ?? []),
  );
  const [selectedFilesMap, setSelectedFilesMap] = useState<Map<number, DriveFile>>(() => {
    const map = new Map<number, DriveFile>();
    return map;
  });
  const { ragStatuses } = useRagStatusPolling(selectedFolder?.id ?? null, token);

  const loadFolders = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const allFolders = await fetchAllPages((skip, limit) => listFolders(token, skip, limit));
      setFolders(allFolders);
    } catch (error) {
      console.error("Failed to load synced folders:", error);
    } finally {
      setLoading(false);
    }
  }, [token]);

  const loadFiles = useCallback(
    async (folderId: number) => {
      if (!token) return;
      setLoading(true);
      try {
        const allFiles = await fetchAllPages((skip, limit) =>
          listFiles(folderId, token, skip, limit),
        );
        setFiles(allFiles);
      } catch (error) {
        console.error("Failed to load files:", error);
      } finally {
        setLoading(false);
      }
    },
    [token],
  );

  useEffect(() => {
    loadFolders();
  }, [loadFolders]);

  const handleFolderClick = (folder: DriveFolder) => {
    setSelectedFolder(folder);
    loadFiles(folder.id);
  };

  const handleBackToFolders = () => {
    setSelectedFolder(null);
    setFiles([]);
  };

  const toggleFileSelection = (fileId: number) => {
    const newSelectedFileIds = new Set(selectedFileIds);
    const newSelectedFilesMap = new Map(selectedFilesMap);
    const file = files.find((f) => f.id === fileId);

    if (newSelectedFileIds.has(fileId)) {
      newSelectedFileIds.delete(fileId);
      newSelectedFilesMap.delete(fileId);
    } else {
      newSelectedFileIds.add(fileId);
      if (file) {
        newSelectedFilesMap.set(fileId, file);
      }
    }
    setSelectedFileIds(newSelectedFileIds);
    setSelectedFilesMap(newSelectedFilesMap);
  };

  const handleConfirmSelection = () => {
    const selectedFiles = Array.from(selectedFilesMap.values()).map((f) => ({
      id: f.id,
      name: f.name,
      mime_type: f.mime_type,
      size: f.size,
    }));
    onFileSelected(selectedFiles);
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[80vh] flex flex-col">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <GoogleDriveIcon className="w-6 h-6" />
            <DialogTitle>Pick a file from Google Drive</DialogTitle>
          </div>
          <DialogDescription>Select a file from your synced folders to attach.</DialogDescription>
        </DialogHeader>

        <nav className="flex" aria-label="Breadcrumb">
          <ol className="flex items-center gap-1 text-sm">
            <li>
              <button
                onClick={handleBackToFolders}
                className={
                  selectedFolder
                    ? "text-primary-600 hover:text-primary-700 dark:text-primary-400"
                    : "text-foreground font-medium"
                }
              >
                Synced Folders
              </button>
            </li>
            {selectedFolder && (
              <li className="flex items-center">
                <ChevronRight className="h-3.5 w-3.5 text-muted-foreground mx-0.5" />
                <span className="text-foreground font-medium">{selectedFolder.name}</span>
              </li>
            )}
          </ol>
        </nav>

        <div className="flex-1 overflow-y-auto -mx-4 sm:-mx-6 px-4 sm:px-6 min-h-[200px]">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Spinner size="md" />
            </div>
          ) : !selectedFolder ? (
            folders.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground text-sm">
                No synced folders. Sync a folder from the Google Drive dashboard first.
              </div>
            ) : (
              <ul className="divide-y divide-border">
                {folders.map((folder) => (
                  <li key={folder.id}>
                    <button
                      onClick={() => handleFolderClick(folder)}
                      className="flex items-center gap-3 w-full text-left py-3 hover:bg-surface-variant/50 -mx-2 px-2 rounded-lg transition-colors"
                    >
                      <Folder className="h-5 w-5 text-warning-500 shrink-0" />
                      <div className="flex flex-col min-w-0">
                        <span className="text-sm text-foreground">{folder.name}</span>
                        <span className="text-xs text-muted-foreground">
                          {folder.file_count} files
                        </span>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )
          ) : files.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground text-sm">
              No files in this folder
            </div>
          ) : (
            <>
              <ul className="divide-y divide-border">
                {files.map((file) => {
                  const ragStatus = ragStatuses[file.id]?.status ?? null;
                  const ragError = ragStatuses[file.id]?.error ?? null;
                  const isReady = ragStatus === "ready";
                  const isSelected = selectedFileIds.has(file.id);
                  return (
                    <li
                      key={file.id}
                      className="flex items-center gap-3 py-3 hover:bg-surface-variant/50 -mx-2 px-2 rounded-lg transition-colors"
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        disabled={!isReady}
                        onChange={() => toggleFileSelection(file.id)}
                        className="w-4 h-4 rounded border-border cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                        aria-label={`Select ${file.name}`}
                      />
                      <FileText className="h-5 w-5 text-secondary-500 shrink-0" />
                      <span className="text-sm text-foreground truncate flex-1 min-w-0">
                        {file.name}
                      </span>
                      <div className="mx-3 shrink-0">
                        <RagStatusIndicator fileId={file.id} status={ragStatus} error={ragError} />
                      </div>
                    </li>
                  );
                })}
              </ul>
              <div className="flex gap-3 mt-6 pt-4 border-t border-border">
                <Button variant="outline" onClick={onClose} className="flex-1">
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  onClick={handleConfirmSelection}
                  disabled={selectedFileIds.size === 0}
                  className="flex-1"
                >
                  Confirm selection
                </Button>
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
