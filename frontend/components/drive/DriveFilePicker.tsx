"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { listFolders, listFiles, DriveFolder, DriveFile } from "@/lib/drive";

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
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 dark:bg-black dark:bg-opacity-75" onClick={onClose}></div>

        <div className="relative bg-white dark:bg-neutral-900 rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] flex flex-col">
          <div className="px-6 py-4 border-b border-gray-200 dark:border-neutral-700">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-medium text-gray-900 dark:text-neutral-100">Pick a file from Google Drive</h3>
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-gray-500 dark:text-neutral-500 dark:hover:text-neutral-300"
              >
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <nav className="flex mt-2" aria-label="Breadcrumb">
              <ol className="flex items-center space-x-1 text-sm">
                <li>
                  <button
                    onClick={handleBackToFolders}
                    className={selectedFolder
                      ? "text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
                      : "text-gray-700 dark:text-neutral-300 font-medium"
                    }
                  >
                    Synced Folders
                  </button>
                </li>
                {selectedFolder && (
                  <li className="flex items-center">
                    <svg className="h-4 w-4 text-gray-400 mx-1" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                    </svg>
                    <span className="text-gray-700 dark:text-neutral-300 font-medium">{selectedFolder.name}</span>
                  </li>
                )}
              </ol>
            </nav>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              </div>
            ) : !selectedFolder ? (
              // Show synced folders
              folders.length === 0 ? (
                <div className="text-center py-8 text-gray-500 dark:text-neutral-400">
                  No synced folders. Sync a folder from the Google Drive dashboard first.
                </div>
              ) : (
                <ul className="divide-y divide-gray-200 dark:divide-neutral-700">
                  {folders.map((folder) => (
                    <li key={folder.id} className="flex items-center py-3 hover:bg-gray-50 dark:hover:bg-neutral-800 px-2 rounded">
                      <button
                        onClick={() => handleFolderClick(folder)}
                        className="flex items-center space-x-3 flex-1 text-left"
                      >
                        <svg className="h-6 w-6 text-yellow-500 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clipRule="evenodd" />
                        </svg>
                        <div className="flex flex-col">
                          <span className="text-sm text-gray-900 dark:text-neutral-100">{folder.name}</span>
                          <span className="text-xs text-gray-500 dark:text-neutral-400">{folder.file_count} files</span>
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )
            ) : (
              // Show files in selected folder
              files.length === 0 ? (
                <div className="text-center py-8 text-gray-500 dark:text-neutral-400">
                  No files in this folder
                </div>
              ) : (
                <ul className="divide-y divide-gray-200 dark:divide-neutral-700">
                  {files.map((file) => (
                    <li key={file.id} className="flex items-center justify-between py-3 hover:bg-gray-50 dark:hover:bg-neutral-800 px-2 rounded">
                      <div className="flex items-center space-x-3 flex-1 min-w-0">
                        <svg className="h-6 w-6 text-blue-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                        </svg>
                        <span className="text-sm text-gray-900 dark:text-neutral-100 truncate">{file.name}</span>
                      </div>
                      <button
                        onClick={() => onFileSelected({
                          id: file.id,
                          name: file.name,
                          mime_type: file.mime_type,
                          size: file.size,
                        })}
                        className="ml-4 px-3 py-1 text-sm font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 shrink-0"
                      >
                        Select
                      </button>
                    </li>
                  ))}
                </ul>
              )
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
