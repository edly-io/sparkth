"use client";

import { useCallback, useEffect, useState } from "react";
import { Folder, FileText, ChevronRight, Loader2 } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/Dialog";
import { listFolders, listFiles, DriveFolder, DriveFile } from "@/lib/drive";
import GoogleDriveIcon from "@/plugins/google-drive/GoogleDriveIcon";

export interface SelectedDriveFile {
  id: number;
  name: string;
  mime_type?: string;
  size?: number;
}

interface DriveFilePickerProps {
  onClose: () => void;
  onFileSelected: (file: SelectedDriveFile) => void;
}

export default function DriveFilePicker({ onClose, onFileSelected }: DriveFilePickerProps) {
  const { token } = useAuth();
  const [folders, setFolders] = useState<DriveFolder[]>([]);
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<DriveFolder | null>(null);
  const [loading, setLoading] = useState(true);

  const loadFolders = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const result = await listFolders(token);
      setFolders(result);
    } catch (error) {
      console.error("Failed to load synced folders:", error);
    } finally {
      setLoading(false);
    }
  }, [token]);

  const loadFiles = useCallback(async (folderId: number) => {
    if (!token) return;
    setLoading(true);
    try {
      const result = await listFiles(folderId, token);
      setFiles(result);
    } catch (error) {
      console.error("Failed to load files:", error);
    } finally {
      setLoading(false);
    }
  }, [token]);

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

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[80vh] flex flex-col">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <GoogleDriveIcon className="w-6 h-6" />
            <DialogTitle>Pick a file from Google Drive</DialogTitle>
          </div>
          <DialogDescription>
            Select a file from your synced folders to attach.
          </DialogDescription>
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
              <Loader2 className="h-6 w-6 animate-spin text-primary-500" />
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
                        <span className="text-xs text-muted-foreground">{folder.file_count} files</span>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )
          ) : (
            files.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground text-sm">
                No files in this folder
              </div>
            ) : (
              <ul className="divide-y divide-border">
                {files.map((file) => (
                  <li
                    key={file.id}
                    className="flex items-center justify-between py-3 hover:bg-surface-variant/50 -mx-2 px-2 rounded-lg transition-colors"
                  >
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <FileText className="h-5 w-5 text-secondary-500 shrink-0" />
                      <span className="text-sm text-foreground truncate">{file.name}</span>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onFileSelected({
                        id: file.id,
                        name: file.name,
                        mime_type: file.mime_type,
                        size: file.size,
                      })}
                    >
                      Select
                    </Button>
                  </li>
                ))}
              </ul>
            )
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
