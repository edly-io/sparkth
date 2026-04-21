"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/lib/auth-context";
import { browseDrive, syncFolder, listFolders, fetchAllPages, DriveBrowseItem } from "@/lib/drive";

interface BreadcrumbItem {
  id: string | undefined;
  name: string;
}

interface UseFolderPickerParams {
  onClose: () => void;
  onFolderSynced: () => void;
}

export function useFolderPicker({ onClose, onFolderSynced }: UseFolderPickerParams) {
  const { token } = useAuth();

  const [items, setItems] = useState<DriveBrowseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncingFolderId, setSyncingFolderId] = useState<string | null>(null);
  const [syncedDriveFolderIds, setSyncedDriveFolderIds] = useState<Set<string>>(new Set());
  const [currentPath, setCurrentPath] = useState<BreadcrumbItem[]>([
    { id: undefined, name: "My Drive" },
  ]);

  const currentFolderId = currentPath[currentPath.length - 1].id;

  // Load already-synced folder IDs once on mount
  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const allFolders = await fetchAllPages((skip, limit) => listFolders(token, skip, limit));
        setSyncedDriveFolderIds(new Set(allFolders.map((f) => f.drive_folder_id)));
      } catch (err) {
        console.error("Failed to load synced folders:", err);
      }
    })();
  }, [token]);

  const loadItems = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    try {
      const result = await browseDrive(currentFolderId, token);
      const folders = result.items.filter((item) => item.is_folder);
      setItems(folders);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to browse Drive";
      setError(message);
      console.error("Failed to browse Drive:", err);
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
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      if (message.includes("already synced")) {
        setSyncedDriveFolderIds((prev) => new Set(prev).add(item.id));
      } else {
        alert(`Failed to sync folder: ${message}`);
      }
    } finally {
      setSyncingFolderId(null);
    }
  };

  return {
    items,
    loading,
    error,
    syncingFolderId,
    syncedDriveFolderIds,
    currentPath,
    currentFolderId,
    handleFolderClick,
    handleBreadcrumbClick,
    handleSync,
  };
}
