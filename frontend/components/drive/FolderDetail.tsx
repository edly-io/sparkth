"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Folder, FileText, RefreshCw, Download, Pencil, Trash2, Upload, Loader2 } from "lucide-react";
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
  formatFileSize,
  formatDate,
} from "@/lib/drive";

interface FolderDetailProps {
  folder: DriveFolder;
  onClose: () => void;
  onFolderChange: () => void;
}

export default function FolderDetail({ folder, onClose, onFolderChange }: FolderDetailProps) {
  const { token } = useAuth();
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [actionFileId, setActionFileId] = useState<number | null>(null);
  const [editingFileId, setEditingFileId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadFiles = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    try {
      const data = await getFolder(folder.id, token);
      setFiles(data.files);
    } catch (error) {
      console.error("Failed to load files:", error);
    } finally {
      setLoading(false);
    }
  }, [token, folder.id]);

  useEffect(() => {
    loadFiles();
  }, [loadFiles]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!token || !e.target.files?.length) return;

    const file = e.target.files[0];
    setUploading(true);
    try {
      await uploadFile(folder.id, file, token);
      await loadFiles();
      onFolderChange();
    } catch (error) {
      alert(`Upload failed: ${error}`);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDownload = async (file: DriveFile) => {
    if (!token) return;

    setActionFileId(file.id);
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
      setActionFileId(null);
    }
  };

  const handleRename = async (file: DriveFile) => {
    if (!token || !editName.trim()) return;

    setActionFileId(file.id);
    try {
      await renameFile(file.id, editName.trim(), token);
      setEditingFileId(null);
      await loadFiles();
    } catch (error) {
      alert(`Rename failed: ${error}`);
    } finally {
      setActionFileId(null);
    }
  };

  const handleDelete = async (file: DriveFile) => {
    if (!token) return;
    if (!confirm(`Delete "${file.name}"? This will also delete it from Google Drive.`)) return;

    setActionFileId(file.id);
    try {
      await deleteFile(file.id, token);
      await loadFiles();
      onFolderChange();
    } catch (error) {
      alert(`Delete failed: ${error}`);
    } finally {
      setActionFileId(null);
    }
  };

  const handleSync = async () => {
    if (!token) return;

    setLoading(true);
    try {
      await refreshFolder(folder.id, token);
      await loadFiles();
      onFolderChange();
    } catch (error) {
      alert(`Sync failed: ${error}`);
    } finally {
      setLoading(false);
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
          <Button variant="ghost" size="icon" onClick={handleSync} disabled={loading} className="h-8 w-8">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto -mx-4 sm:-mx-6 min-h-[200px]">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-primary-500" />
            </div>
          ) : files.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="mx-auto h-10 w-10 text-muted-foreground/40 mb-3" />
              <p className="text-sm text-muted-foreground">No files in this folder</p>
            </div>
          ) : (
            <table className="min-w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-6 py-2.5 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Name</th>
                  <th className="px-6 py-2.5 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Size</th>
                  <th className="px-6 py-2.5 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Modified</th>
                  <th className="px-6 py-2.5 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {files.map((file) => (
                  <tr key={file.id} className="hover:bg-surface-variant/50 transition-colors">
                    <td className="px-6 py-3 whitespace-nowrap">
                      <div className="flex items-center gap-3">
                        <FileText className="h-4 w-4 text-secondary-500 shrink-0" />
                        {editingFileId === file.id ? (
                          <input
                            type="text"
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") handleRename(file);
                              if (e.key === "Escape") setEditingFileId(null);
                            }}
                            className="text-sm text-foreground bg-input border border-border rounded-md px-2 py-1 focus:border-primary-500 focus:outline-none"
                            autoFocus
                          />
                        ) : (
                          <span className="text-sm text-foreground">{file.name}</span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-3 whitespace-nowrap text-sm text-muted-foreground">{formatFileSize(file.size)}</td>
                    <td className="px-6 py-3 whitespace-nowrap text-sm text-muted-foreground">{formatDate(file.modified_time)}</td>
                    <td className="px-6 py-3 whitespace-nowrap text-right">
                      <div className="flex justify-end gap-1">
                        {editingFileId === file.id ? (
                          <>
                            <Button variant="ghost" size="sm" onClick={() => handleRename(file)} disabled={actionFileId === file.id}>
                              Save
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => setEditingFileId(null)}>
                              Cancel
                            </Button>
                          </>
                        ) : (
                          <>
                            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => handleDownload(file)} disabled={actionFileId === file.id}>
                              <Download className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => { setEditingFileId(file.id); setEditName(file.name); }} disabled={actionFileId === file.id}>
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-error-500" onClick={() => handleDelete(file)} disabled={actionFileId === file.id}>
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <DialogFooter className="!justify-between">
          <div>
            <input ref={fileInputRef} type="file" onChange={handleUpload} className="hidden" id="folder-file-upload" />
            <Button variant="primary" size="sm" onClick={() => fileInputRef.current?.click()} loading={uploading}>
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
