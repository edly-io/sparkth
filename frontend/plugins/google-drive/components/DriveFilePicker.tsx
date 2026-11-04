"use client";

import { useCallback, useEffect, useReducer } from "react";
import { Folder, FileText, ChevronRight } from "lucide-react";
import { Spinner } from "@/lib/components/ui/Spinner";
import { useAuth } from "@/lib/auth/hooks";
import { Button } from "@/lib/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/lib/components/ui/Dialog";
import { listFolders, listFiles, fetchAllPages } from "@/plugins/google-drive/client";
import { DriveFolder, DriveFile, RagStatus } from "@/plugins/google-drive/types";
import { useRagStatusPolling } from "@/plugins/google-drive/hooks/useRagStatusPolling";
import { RagStatusIndicator } from "@/plugins/google-drive/components/RagStatusIndicator";
import GoogleDriveIcon from "@/plugins/google-drive/GoogleDriveIcon";

/** A file the user picked, identified by its document, which also keys the picker's selection. */
export interface SelectedDriveFile {
  document_id: number;
  name: string;
  mime_type?: string;
  size?: number;
}

interface DriveFilePickerProps {
  onClose: () => void;
  onFileSelected: (files: SelectedDriveFile[]) => void;
  initialSelectedFiles?: SelectedDriveFile[];
}

const EMPTY_INITIAL_SELECTED_FILES: SelectedDriveFile[] = [];

interface PickerState {
  folders: DriveFolder[];
  files: DriveFile[];
  selectedFolder: DriveFolder | null;
  loading: boolean;
  /** The picked files, keyed by `document_id`. */
  selectedFiles: Map<number, SelectedDriveFile>;
}

type PickerAction =
  | { type: "SET_FOLDERS"; folders: DriveFolder[] }
  | { type: "SET_FILES"; files: DriveFile[] }
  | { type: "SET_LOADING"; loading: boolean }
  | { type: "SELECT_FOLDER"; folder: DriveFolder }
  | { type: "BACK_TO_FOLDERS" }
  | { type: "TOGGLE_FILE_SELECTION"; file: DriveFile };

function pickerReducer(state: PickerState, action: PickerAction): PickerState {
  switch (action.type) {
    case "SET_FOLDERS":
      return { ...state, folders: action.folders };
    case "SET_FILES":
      return { ...state, files: action.files };
    case "SET_LOADING":
      return { ...state, loading: action.loading };
    case "SELECT_FOLDER":
      return { ...state, selectedFolder: action.folder };
    case "BACK_TO_FOLDERS":
      return { ...state, selectedFolder: null, files: [] };
    case "TOGGLE_FILE_SELECTION": {
      const { file } = action;
      if (file.document_id == null) return state;
      const selected = new Map(state.selectedFiles);
      if (selected.has(file.document_id)) {
        selected.delete(file.document_id);
      } else {
        selected.set(file.document_id, {
          document_id: file.document_id,
          name: file.name,
          mime_type: file.mime_type ?? undefined,
          size: file.size ?? undefined,
        });
      }
      return { ...state, selectedFiles: selected };
    }
  }
}

function buildInitialState(initialSelectedFiles: SelectedDriveFile[]): PickerState {
  return {
    folders: [],
    files: [],
    selectedFolder: null,
    loading: true,
    selectedFiles: new Map(initialSelectedFiles.map((f) => [f.document_id, f])),
  };
}

export default function DriveFilePicker({
  onClose,
  onFileSelected,
  initialSelectedFiles = EMPTY_INITIAL_SELECTED_FILES,
}: DriveFilePickerProps) {
  const { token } = useAuth();
  const [state, dispatch] = useReducer(pickerReducer, initialSelectedFiles, buildInitialState);
  const { folders, files, selectedFolder, loading, selectedFiles } = state;
  const { ragStatuses } = useRagStatusPolling(
    selectedFolder?.id != null ? [selectedFolder.id] : [],
    token,
  );

  const loadFolders = useCallback(async () => {
    if (!token) return;
    dispatch({ type: "SET_LOADING", loading: true });
    try {
      const allFolders = await fetchAllPages((skip, limit) => listFolders(token, skip, limit));
      dispatch({ type: "SET_FOLDERS", folders: allFolders });
    } catch (error) {
      console.error("Failed to load synced folders:", error);
    } finally {
      dispatch({ type: "SET_LOADING", loading: false });
    }
  }, [token]);

  const loadFiles = useCallback(
    async (folderId: number) => {
      if (!token) return;
      dispatch({ type: "SET_LOADING", loading: true });
      try {
        const allFiles = await fetchAllPages((skip, limit) =>
          listFiles(folderId, token, skip, limit),
        );
        dispatch({ type: "SET_FILES", files: allFiles });
      } catch (error) {
        console.error("Failed to load files:", error);
      } finally {
        dispatch({ type: "SET_LOADING", loading: false });
      }
    },
    [token],
  );

  useEffect(() => {
    loadFolders();
  }, [loadFolders]);

  const handleFolderClick = (folder: DriveFolder) => {
    dispatch({ type: "SELECT_FOLDER", folder });
    loadFiles(folder.id);
  };

  const handleBackToFolders = () => {
    dispatch({ type: "BACK_TO_FOLDERS" });
  };

  const toggleFileSelection = (fileId: number) => {
    const file = files.find((f) => f.id === fileId);
    if (!file) return;
    dispatch({ type: "TOGGLE_FILE_SELECTION", file });
  };

  const handleConfirmSelection = () => {
    onFileSelected([...selectedFiles.values()]);
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
                  const canAttach = ragStatus === RagStatus.Ready && file.document_id != null;
                  const isSelected =
                    file.document_id != null && selectedFiles.has(file.document_id);
                  return (
                    <li
                      key={file.id}
                      className="flex items-center gap-3 py-3 hover:bg-surface-variant/50 -mx-2 px-2 rounded-lg transition-colors"
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        disabled={!canAttach}
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
                  disabled={selectedFiles.size === 0 && initialSelectedFiles.length === 0}
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
