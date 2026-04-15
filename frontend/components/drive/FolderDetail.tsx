"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import { useRagStatusPolling } from "@/lib/useRagStatusPolling";
import { Folder, FileText, RefreshCw, Upload } from "lucide-react";
import { FileTable } from "./FileTable";
import { Spinner } from "@/components/Spinner";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/Dialog";
import {
  DriveFolder,
  DriveFile,
  getFolder,
  uploadFile,
  downloadFile,
  renameFile,
  deleteFile,
  refreshFolder,
} from "@/lib/drive";

interface FolderDetailProps {
  folder: DriveFolder;
  onClose: () => void;
  onFolderChange: () => void;
}

interface FolderDetailState {
  files: DriveFile[];
  loading: boolean;
  uploading: boolean;
  actionFileId: number | null;
  editingFileId: number | null;
  editName: string;
}

export type FolderDetailAction =
  | { type: "SET_FILES"; files: DriveFile[] }
  | { type: "SET_LOADING"; loading: boolean }
  | { type: "SET_UPLOADING"; uploading: boolean }
  | { type: "SET_ACTION_FILE"; id: number | null }
  | { type: "START_EDIT"; fileId: number; name: string }
  | { type: "CANCEL_EDIT" }
  | { type: "SET_EDIT_NAME"; name: string };

function folderDetailReducer(
  state: FolderDetailState,
  action: FolderDetailAction,
): FolderDetailState {
  switch (action.type) {
    case "SET_FILES":
      return { ...state, files: action.files };
    case "SET_LOADING":
      return { ...state, loading: action.loading };
    case "SET_UPLOADING":
      return { ...state, uploading: action.uploading };
    case "SET_ACTION_FILE":
      return { ...state, actionFileId: action.id };
    case "START_EDIT":
      return { ...state, editingFileId: action.fileId, editName: action.name };
    case "CANCEL_EDIT":
      return { ...state, editingFileId: null };
    case "SET_EDIT_NAME":
      return { ...state, editName: action.name };
  }
}

const initialState: FolderDetailState = {
  files: [],
  loading: true,
  uploading: false,
  actionFileId: null,
  editingFileId: null,
  editName: "",
};

export default function FolderDetail({ folder, onClose, onFolderChange }: FolderDetailProps) {
  const { token } = useAuth();
  const [state, dispatch] = useReducer(folderDetailReducer, initialState);
  const { files, loading, uploading, actionFileId, editingFileId, editName } = state;
  const { ragStatuses, restart: restartRagPolling } = useRagStatusPolling(folder.id, token);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadFiles = useCallback(async () => {
    if (!token) return;

    dispatch({ type: "SET_LOADING", loading: true });
    try {
      const data = await getFolder(folder.id, token);
      dispatch({ type: "SET_FILES", files: data.files });
    } catch (error) {
      console.error("Failed to load files:", error);
    } finally {
      dispatch({ type: "SET_LOADING", loading: false });
    }
  }, [token, folder.id]);

  useEffect(() => {
    loadFiles();
  }, [loadFiles]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!token || !e.target.files?.length) return;

    const file = e.target.files[0];
    dispatch({ type: "SET_UPLOADING", uploading: true });
    try {
      await uploadFile(folder.id, file, token);
      await loadFiles();
      onFolderChange();
      restartRagPolling();
    } catch (error) {
      alert(`Upload failed: ${error}`);
    } finally {
      dispatch({ type: "SET_UPLOADING", uploading: false });
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDownload = async (file: DriveFile) => {
    if (!token) return;

    dispatch({ type: "SET_ACTION_FILE", id: file.id });
    try {
      const blob = await downloadFile(file.id, token);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = file.name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      alert(`Download failed: ${error}`);
    } finally {
      dispatch({ type: "SET_ACTION_FILE", id: null });
    }
  };

  const handleRename = async (file: DriveFile) => {
    if (!token || !editName.trim()) return;

    dispatch({ type: "SET_ACTION_FILE", id: file.id });
    try {
      await renameFile(file.id, editName.trim(), token);
      dispatch({ type: "CANCEL_EDIT" });
      await loadFiles();
    } catch (error) {
      alert(`Rename failed: ${error}`);
    } finally {
      dispatch({ type: "SET_ACTION_FILE", id: null });
    }
  };

  const handleDelete = async (file: DriveFile) => {
    if (!token) return;
    if (!confirm(`Delete "${file.name}"? This will also delete it from Google Drive.`)) return;

    dispatch({ type: "SET_ACTION_FILE", id: file.id });
    try {
      await deleteFile(file.id, token);
      await loadFiles();
      onFolderChange();
    } catch (error) {
      alert(`Delete failed: ${error}`);
    } finally {
      dispatch({ type: "SET_ACTION_FILE", id: null });
    }
  };

  const handleSync = async () => {
    if (!token) return;

    dispatch({ type: "SET_LOADING", loading: true });
    try {
      await refreshFolder(folder.id, token);
      await loadFiles();
      onFolderChange();
      restartRagPolling();
    } catch (error) {
      alert(`Sync failed: ${error}`);
    } finally {
      dispatch({ type: "SET_LOADING", loading: false });
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <Folder className="h-6 w-6 text-warning-500 shrink-0" />
            <div>
              <DialogTitle>{folder.name}</DialogTitle>
              <DialogDescription>{files.length} files</DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="flex items-center justify-end -mt-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={handleSync}
            disabled={loading}
            aria-label="Sync folder"
            className="h-8 w-8"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto -mx-4 sm:-mx-6 min-h-[200px]">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Spinner size="md" />
            </div>
          ) : files.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="mx-auto h-10 w-10 text-muted-foreground/40 mb-3" />
              <p className="text-sm text-muted-foreground">No files in this folder</p>
            </div>
          ) : (
            <FileTable
              files={files}
              editingFileId={editingFileId}
              editName={editName}
              actionFileId={actionFileId}
              ragStatuses={ragStatuses}
              dispatch={dispatch}
              onDownload={handleDownload}
              onRename={handleRename}
              onDelete={handleDelete}
            />
          )}
        </div>

        <DialogFooter className="!justify-between">
          <div>
            <input
              ref={fileInputRef}
              type="file"
              onChange={handleUpload}
              className="hidden"
              id="folder-file-upload"
            />
            <Button
              variant="primary"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              loading={uploading}
            >
              <Upload className="w-4 h-4 mr-2" />
              Upload File
            </Button>
          </div>
          <Button variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
