"use client";

import React, { createContext, useState, useCallback } from "react";

/** The sidebar's state and the functions that change it. */
export interface SidebarContextType {
  // Mobile sidebar state
  isOpen: boolean;
  open: () => void;
  close: () => void;
  toggle: () => void;
  // Desktop sidebar collapsed state
  isCollapsed: boolean;
  setCollapsed: (collapsed: boolean) => void;
  toggleCollapsed: () => void;
}

/** The sidebar context, read through `useSidebar`. It is undefined outside a `SidebarProvider`. */
export const SidebarContext = createContext<SidebarContextType | undefined>(undefined);

/** Holds whether the mobile sidebar is open and the desktop sidebar is collapsed. Both start false. */
export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);
  const toggle = useCallback(() => setIsOpen((prev) => !prev), []);

  const setCollapsed = useCallback((collapsed: boolean) => setIsCollapsed(collapsed), []);
  const toggleCollapsed = useCallback(() => setIsCollapsed((prev) => !prev), []);

  return (
    <SidebarContext.Provider
      value={{
        isOpen,
        open,
        close,
        toggle,
        isCollapsed,
        setCollapsed,
        toggleCollapsed,
      }}
    >
      {children}
    </SidebarContext.Provider>
  );
}
