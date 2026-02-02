"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { useRouter, useSearchParams } from "next/navigation";
import SparkthHeader from "@/components/SparkthHeader";
import ConnectionStatus from "@/components/drive/ConnectionStatus";
import FolderList from "@/components/drive/FolderList";
import FolderPicker from "@/components/drive/FolderPicker";
import {
  getConnectionStatus,
  listFolders,
  DriveFolder,
  ConnectionStatus as ConnectionStatusType,
} from "@/lib/drive";

function DrivePageContent() {
  const { token, isAuthenticated, logout } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatusType | null>(null);
  const [folders, setFolders] = useState<DriveFolder[]>([]);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);
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
    setMounted(true);
  }, []);

  useEffect(() => {
    if (mounted && !isAuthenticated) {
      router.replace("/login");
    }
  }, [mounted, isAuthenticated, router]);

  useEffect(() => {
    if (mounted && isAuthenticated) {
      loadData();
    }
  }, [mounted, isAuthenticated, loadData]);

  // Handle OAuth callback
  useEffect(() => {
    if (searchParams.get("connected") === "true") {
      loadData();
      // Clear the query param
      router.replace("/drive");
    }
  }, [searchParams, loadData, router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <SparkthHeader isAuthenticated={isAuthenticated} logout={logout} />

      <div className="max-w-6xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Google Drive</h1>
          <p className="mt-2 text-sm text-gray-600">
            Manage your synced folders and files
          </p>
        </div>

        <ConnectionStatus
          status={connectionStatus}
          onStatusChange={loadData}
        />

        {connectionStatus?.connected && (
          <>
            <div className="mt-8 mb-4 flex justify-between items-center">
              <h2 className="text-xl font-semibold text-gray-900">Synced Folders</h2>
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

export default function DrivePage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-screen">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Loading...</p>
          </div>
        </div>
      }
    >
      <DrivePageContent />
    </Suspense>
  );
}
