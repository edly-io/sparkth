"use client";

import { useSyncExternalStore } from "react";

function getServerSnapshot(): boolean {
  return false;
}

function useMediaQuery(query: string): boolean {
  const subscribe = (callback: () => void) => {
    const media = window.matchMedia(query);
    media.addEventListener("change", callback);
    return () => media.removeEventListener("change", callback);
  };

  const getSnapshot = () => {
    return window.matchMedia(query).matches;
  };

  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

// Mobile: < 640px
export function useIsMobile(): boolean {
  return useMediaQuery("(max-width: 639px)");
}

// Tablet: 640px - 1023px
export function useIsTablet(): boolean {
  return useMediaQuery("(min-width: 640px) and (max-width: 1023px)");
}

// Desktop: >= 1024px
export function useIsDesktop(): boolean {
  return useMediaQuery("(min-width: 1024px)");
}

export { useMediaQuery };
