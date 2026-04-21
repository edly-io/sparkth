"use client";

import { useState, useEffect } from "react";
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

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    (async () => {
      try {
        const allFolders = await fetchAllPages((skip, limit) => listFolders(token, skip, limit));
        if (!controller.signal.aborted) {
          setSyncedDriveFolderIds(new Set(allFolders.map((f) => f.drive_folder_id)));
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          console.error("Failed to load synced folders:", err);
        }
      }
    })();
    return () => controller.abort();
  }, [token]);

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    setLoading(true);
    (async () => {
      try {
        const result = await browseDrive(currentFolderId, token);
        if (!controller.signal.aborted) {
          const folders = result.items.filter((item) => item.is_folder);
          setItems(folders);
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          const message = err instanceof Error ? err.message : "Failed to browse Drive";
          setError(message);
          console.error("Failed to browse Drive:", err);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    })();
    return () => controller.abort();
  }, [token, currentFolderId]);

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
