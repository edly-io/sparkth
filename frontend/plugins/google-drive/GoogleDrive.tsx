"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, FolderSync } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/Button";
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
    if (!token) {
      setLoading(false);
      return;
    }

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
          <Loader2 className="h-10 w-10 animate-spin text-primary-500 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-border px-6 py-4">
        <div className="flex items-center gap-3">
          <GoogleDriveIcon className="w-8 h-8" />
          <div>
            <h2 className="text-lg font-semibold text-foreground">Google Drive</h2>
            <p className="text-sm text-muted-foreground">Manage your synced folders and files</p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        <ConnectionStatus status={connectionStatus} onStatusChange={loadData} />

        {connectionStatus?.connected && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-base font-semibold text-foreground">Synced Folders</h3>
              <Button variant="primary" size="sm" onClick={() => setShowFolderPicker(true)}>
                <FolderSync className="w-4 h-4 mr-2" />
                Sync Folder
              </Button>
            </div>

            <FolderList folders={folders} onFoldersChange={loadData} />
          </div>
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
