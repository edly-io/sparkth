"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import ConnectionStatus from "@/components/drive/ConnectionStatus";
import FolderList from "@/components/drive/FolderList";
import FolderPicker from "@/components/drive/FolderPicker";
import GoogleDriveIcon from "./GoogleDriveIcon";
import {
  getConnectionStatus,
  listFolders,
  DriveFolder,
  ConnectionStatus as ConnectionStatusType,
} from "@/lib/drive";

export default function GoogleDrive() {
  const { token } = useAuth();

  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatusType | null>(null);
  const [folders, setFolders] = useState<DriveFolder[]>([]);
  const [loading, setLoading] = useState(true);
  const [showFolderPicker, setShowFolderPicker] = useState(false);

  const loadData = useCallback(async () => {
    if (!token) return;

    try {
      const status = await getConnectionStatus(token);
      setConnectionStatus(status);

      if (status.connected) {
        const folderList = await listFolders(token);
        setFolders(folderList);
      }
    } catch (error) {
      console.error("Failed to load data:", error);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="border-b px-6 py-4">
        <div className="flex items-center gap-3">
          <GoogleDriveIcon className="w-8 h-8 text-blue-500" />
          <div>
            <h2 className="text-lg font-semibold text-edly-gray-700">
              Google Drive
            </h2>
            <p className="text-sm text-edly-gray-600">
              Manage your synced folders and files
            </p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <ConnectionStatus
          status={connectionStatus}
          onStatusChange={loadData}
        />

        {connectionStatus?.connected && (
          <>
            <div className="mt-8 mb-4 flex justify-between items-center">
              <h3 className="text-lg font-semibold text-gray-900">Synced Folders</h3>
              <button
                onClick={() => setShowFolderPicker(true)}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
              >
                + Sync Folder
              </button>
            </div>

            <FolderList
              folders={folders}
              onFoldersChange={loadData}
            />
          </>
        )}
      </div>

      {showFolderPicker && (
        <FolderPicker
          onClose={() => setShowFolderPicker(false)}
          onFolderSynced={loadData}
        />
      )}
    </div>
  );
}
