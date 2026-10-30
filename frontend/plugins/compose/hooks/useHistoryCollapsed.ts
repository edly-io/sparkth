"use client";

import { useCallback, useEffect, useState } from "react";

export const HISTORY_COLLAPSED_KEY = "sparkth.chat.historyCollapsed";

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(HISTORY_COLLAPSED_KEY) === "true";
  } catch {
    // Storage can be blocked (private mode, disabled site data); fall back to expanded.
    return false;
  }
}

function writeCollapsed(collapsed: boolean): void {
  try {
    localStorage.setItem(HISTORY_COLLAPSED_KEY, String(collapsed));
  } catch {
    // Without storage the flag only lasts for this page view.
  }
}

/**
 * Whether the chat history column is collapsed, remembered per browser.
 *
 * Starts expanded and reads the stored flag after mount, so the first client render matches
 * the server render.
 */
export function useHistoryCollapsed(): [boolean, (collapsed: boolean) => void] {
  const [collapsed, setCollapsedState] = useState(false);

  useEffect(() => {
    setCollapsedState(readCollapsed());
  }, []);

  const setCollapsed = useCallback((next: boolean) => {
    setCollapsedState(next);
    writeCollapsed(next);
  }, []);

  return [collapsed, setCollapsed];
}
