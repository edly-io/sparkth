import { use } from "react";
import { SidebarContext, type SidebarContextType } from "@/core/sidebar/context";

/** The sidebar's state. Throws outside a `SidebarProvider`. */
export function useSidebar(): SidebarContextType {
  const context = use(SidebarContext);
  if (context === undefined) {
    throw new Error("useSidebar must be used within a SidebarProvider");
  }
  return context;
}
