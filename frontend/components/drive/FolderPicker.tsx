"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { browseDrive, syncFolder, DriveBrowseItem } from "@/lib/drive";

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
  const [syncingFolderId, setSyncingFolderId] = useState<string | null>(null);
  const [currentPath, setCurrentPath] = useState<BreadcrumbItem[]>([
    { id: undefined, name: "My Drive" },
  ]);

  const currentFolderId = currentPath[currentPath.length - 1].id;

  const loadItems = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    try {
      const result = await browseDrive(currentFolderId, token);
      // Filter to show only folders
      const folders = result.items.filter((item) => item.is_folder);
      setItems(folders);
    } catch (error) {
      console.error("Failed to browse Drive:", error);
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
    } catch (error) {
      alert(`Failed to sync folder: ${error}`);
    } finally {
      setSyncingFolderId(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={onClose}></div>

        <div className="relative bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] flex flex-col">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-medium text-gray-900">Select a folder to sync</h3>
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

            {/* Breadcrumb */}
            <nav className="flex mt-2" aria-label="Breadcrumb">
              <ol className="flex items-center space-x-1 text-sm">
                {currentPath.map((item, index) => (
                  <li key={index} className="flex items-center">
                    {index > 0 && (
                      <svg
                        className="h-4 w-4 text-gray-400 mx-1"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path
                          fillRule="evenodd"
                          d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                          clipRule="evenodd"
                        />
                      </svg>
                    )}
                    <button
                      onClick={() => handleBreadcrumbClick(index)}
                      className={`${
                        index === currentPath.length - 1
                          ? "text-gray-700 font-medium"
                          : "text-blue-600 hover:text-blue-800"
                      }`}
                    >
                      {item.name}
                    </button>
                  </li>
                ))}
              </ol>
            </nav>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              </div>
            ) : items.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                No folders found in this location
              </div>
            ) : (
              <ul className="divide-y divide-gray-200">
                {items.map((item) => (
                  <li key={item.id} className="flex items-center justify-between py-3 hover:bg-gray-50">
                    <button
                      onClick={() => handleFolderClick(item)}
                      className="flex items-center space-x-3 flex-1 text-left"
                    >
                      <svg
                        className="h-6 w-6 text-yellow-500"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path
                          fillRule="evenodd"
                          d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"
                          clipRule="evenodd"
                        />
                      </svg>
                      <span className="text-sm text-gray-900">{item.name}</span>
                    </button>
                    <button
                      onClick={() => handleSync(item)}
                      disabled={syncingFolderId !== null}
                      className="ml-4 px-3 py-1 text-sm font-medium text-blue-600 hover:text-blue-800 disabled:opacity-50"
                    >
                      {syncingFolderId === item.id ? "Syncing..." : "Sync"}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
