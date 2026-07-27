"use client";

import { Sheet, SheetContent } from "@/components/ui/Sheet";
import { useSidebar } from "@/lib/sidebar-context";
import AppSidebar from "./AppSidebar";

interface MobileSidebarProps {
  user?: {
    name?: string;
    email?: string;
    avatar?: string;
    plan?: string;
  };
  navPermissions?: Record<string, boolean>;
  onLogout?: () => void;
}

export default function MobileSidebar({ user, navPermissions, onLogout }: MobileSidebarProps) {
  const { isOpen, close } = useSidebar();

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && close()}>
      <SheetContent side="left" className="p-0 w-64" hideCloseButton>
        <AppSidebar
          user={user}
          navPermissions={navPermissions}
          onLogout={onLogout}
          variant="mobile"
          onNavigate={close}
        />
      </SheetContent>
    </Sheet>
  );
}
