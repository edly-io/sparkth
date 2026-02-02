"use client";

import React, { createContext, useContext, useState, useCallback } from "react";

interface SidebarContextType {
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

const SidebarContext = createContext<SidebarContextType | undefined>(undefined);

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);
  const toggle = useCallback(() => setIsOpen((prev) => !prev), []);

  const setCollapsed = useCallback((collapsed: boolean) => setIsCollapsed(collapsed), []);
  const toggleCollapsed = useCallback(() => setIsCollapsed((prev) => !prev), []);

  return (
    <SidebarContext.Provider value={{
      isOpen,
      open,
      close,
      toggle,
      isCollapsed,
      setCollapsed,
      toggleCollapsed,
    }}>
      {children}
    </SidebarContext.Provider>
  );
}

export function useSidebar(): SidebarContextType {
  const context = useContext(SidebarContext);
  if (context === undefined) {
    throw new Error("useSidebar must be used within a SidebarProvider");
  }
  return context;
}
