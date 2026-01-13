"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth-context";
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
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
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

    if (!confirm(`Delete "${file.name}"? This will also delete it from Google Drive.`)) {
      return;
    }

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

  const startRename = (file: DriveFile) => {
    setEditingFileId(file.id);
    setEditName(file.name);
  };

  const getFileIcon = (mimeType?: string) => {
    if (!mimeType) return "text-gray-400";
    if (mimeType.startsWith("image/")) return "text-purple-500";
    if (mimeType.startsWith("video/")) return "text-red-500";
    if (mimeType.includes("pdf")) return "text-red-600";
    if (mimeType.includes("spreadsheet") || mimeType.includes("excel")) return "text-green-600";
    if (mimeType.includes("document") || mimeType.includes("word")) return "text-blue-600";
    if (mimeType.includes("presentation") || mimeType.includes("powerpoint")) return "text-orange-500";
    return "text-gray-400";
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={onClose}></div>

        <div className="relative bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[80vh] flex flex-col">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <svg
                  className="h-8 w-8 text-yellow-500"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"
                    clipRule="evenodd"
                  />
                </svg>
                <div>
                  <h3 className="text-lg font-medium text-gray-900">{folder.name}</h3>
                  <p className="text-sm text-gray-500">{files.length} files</p>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={handleSync}
                  disabled={loading}
                  className="p-2 text-gray-400 hover:text-blue-600 disabled:opacity-50"
                  title="Sync"
                >
                  <svg
                    className={`h-5 w-5 ${loading ? "animate-spin" : ""}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                    />
                  </svg>
                </button>
                <button
                  onClick={onClose}
                  className="text-gray-400 hover:text-gray-500"
                >
                  <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              </div>
            ) : files.length === 0 ? (
              <div className="text-center py-12">
                <svg
                  className="mx-auto h-12 w-12 text-gray-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                  />
                </svg>
                <p className="mt-2 text-sm text-gray-500">No files in this folder</p>
              </div>
            ) : (
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Name
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Size
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Modified
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {files.map((file) => (
                    <tr key={file.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <svg
                            className={`h-5 w-5 mr-3 ${getFileIcon(file.mime_type)}`}
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                            />
                          </svg>
                          {editingFileId === file.id ? (
                            <input
                              type="text"
                              value={editName}
                              onChange={(e) => setEditName(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") handleRename(file);
                                if (e.key === "Escape") setEditingFileId(null);
                              }}
                              className="text-sm text-gray-900 border rounded px-2 py-1"
                              autoFocus
                            />
                          ) : (
                            <span className="text-sm text-gray-900">{file.name}</span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {formatFileSize(file.size)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {formatDate(file.modified_time)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <div className="flex justify-end space-x-2">
                          {editingFileId === file.id ? (
                            <>
                              <button
                                onClick={() => handleRename(file)}
                                disabled={actionFileId === file.id}
                                className="text-green-600 hover:text-green-900"
                              >
                                Save
                              </button>
                              <button
                                onClick={() => setEditingFileId(null)}
                                className="text-gray-600 hover:text-gray-900"
                              >
                                Cancel
                              </button>
                            </>
                          ) : (
                            <>
                              <button
                                onClick={() => handleDownload(file)}
                                disabled={actionFileId === file.id}
                                className="text-blue-600 hover:text-blue-900 disabled:opacity-50"
                              >
                                Download
                              </button>
                              <button
                                onClick={() => startRename(file)}
                                disabled={actionFileId === file.id}
                                className="text-gray-600 hover:text-gray-900 disabled:opacity-50"
                              >
                                Rename
                              </button>
                              <button
                                onClick={() => handleDelete(file)}
                                disabled={actionFileId === file.id}
                                className="text-red-600 hover:text-red-900 disabled:opacity-50"
                              >
                                Delete
                              </button>
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

          <div className="px-6 py-4 border-t border-gray-200">
            <div className="flex justify-between items-center">
              <div>
                <input
                  ref={fileInputRef}
                  type="file"
                  onChange={handleUpload}
                  className="hidden"
                  id="file-upload"
                />
                <label
                  htmlFor="file-upload"
                  className={`inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 cursor-pointer ${
                    uploading ? "opacity-50 cursor-not-allowed" : ""
                  }`}
                >
                  {uploading ? "Uploading..." : "Upload File"}
                </label>
              </div>
              <button
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
