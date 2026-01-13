"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth-context";
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

    if (!confirm(`Remove "${folder.name}" from Sparkth? This won't delete files from Google Drive.`)) {
      return;
    }

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

  const getSyncStatusColor = (status: string) => {
    switch (status) {
      case "synced":
        return "text-green-600 bg-green-100";
      case "syncing":
        return "text-blue-600 bg-blue-100";
      case "error":
        return "text-red-600 bg-red-100";
      default:
        return "text-gray-600 bg-gray-100";
    }
  };

  if (folders.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow-sm p-12 text-center">
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
            d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
          />
        </svg>
        <h3 className="mt-2 text-sm font-medium text-gray-900">No folders synced</h3>
        <p className="mt-1 text-sm text-gray-500">
          Click &quot;Sync Folder&quot; to add a Google Drive folder.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        <ul className="divide-y divide-gray-200">
          {folders.map((folder) => (
            <li
              key={folder.id}
              className="p-4 hover:bg-gray-50 cursor-pointer"
              onClick={() => setSelectedFolder(folder)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
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
                    <p className="text-sm font-medium text-gray-900">{folder.name}</p>
                    <p className="text-xs text-gray-500">
                      {folder.file_count} file{folder.file_count !== 1 ? "s" : ""}
                      {folder.last_synced_at && ` • Last synced ${formatDate(folder.last_synced_at)}`}
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-3" onClick={(e) => e.stopPropagation()}>
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getSyncStatusColor(folder.sync_status)}`}
                  >
                    {folder.sync_status}
                  </span>

                  <button
                    onClick={() => handleRefresh(folder)}
                    disabled={loadingId === folder.id}
                    className="p-2 text-gray-400 hover:text-blue-600 disabled:opacity-50"
                    title="Sync"
                  >
                    <svg
                      className={`h-5 w-5 ${loadingId === folder.id ? "animate-spin" : ""}`}
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
                    onClick={() => handleRemove(folder)}
                    disabled={loadingId === folder.id}
                    className="p-2 text-gray-400 hover:text-red-600 disabled:opacity-50"
                    title="Remove"
                  >
                    <svg
                      className="h-5 w-5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                      />
                    </svg>
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>

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
