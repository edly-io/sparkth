"use client";

import { useState, useEffect } from "react";
import "@/app/plugins";
import { useAuth } from "@/core/auth/hooks";
import { resolveSidebarPermissions } from "@/core/sidebar/gatedSidebarLinks";
import { PluginProvider } from "@/core/plugins/context";
import AppSidebar from "@/core/sidebar/components/layout/AppSidebar";
import MobileSidebar from "@/core/sidebar/components/layout/MobileSidebar";
import { SidebarProvider } from "@/core/sidebar/context";
import { useSidebar } from "@/core/sidebar/hooks";
import { redirect } from "next/navigation";
import { Menu } from "lucide-react";
import { Spinner } from "@/core/components/ui/Spinner";
import { Button } from "@/core/components/ui/Button";
import { SparkthLogo } from "@/core/components/ui/SparkthLogo";
import { ThemeToggle } from "@/core/theme/components/ui/ThemeToggle";

function MobileHeader() {
  const { toggle } = useSidebar();
  return (
    <div className="lg:hidden flex items-center justify-between px-2 py-2 border-b border-border bg-card">
      <Button variant="ghost" size="icon" onClick={toggle} aria-label="Open menu">
        <Menu className="h-6 w-6" />
      </Button>
      <SparkthLogo size={48} />
      <ThemeToggle />
    </div>
  );
}

function DashboardContent({
  children,
  user,
  logout,
  sidebarPermissions,
}: {
  children: React.ReactNode;
  user: {
    name?: string;
    email?: string;
    avatar?: string;
    plan?: string;
  };
  logout: () => void;
  sidebarPermissions: Record<string, boolean>;
}) {
  const { isCollapsed, toggleCollapsed } = useSidebar();

  return (
    <div className="flex flex-col h-screen">
      <MobileHeader />
      <div className="flex flex-1 overflow-hidden">
        <div className="hidden lg:block">
          <AppSidebar
            user={user}
            sidebarPermissions={sidebarPermissions}
            onLogout={logout}
            variant="desktop"
            isCollapsed={isCollapsed}
            onToggleCollapse={toggleCollapsed}
          />
        </div>
        <MobileSidebar user={user} sidebarPermissions={sidebarPermissions} onLogout={logout} />
        <main className="flex-1 overflow-auto bg-background relative">
          <div className="absolute top-3 right-3 z-10 hidden lg:block">
            <ThemeToggle />
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { token, user, isAuthenticated, loading, logout } = useAuth();

  const [sidebarPermissions, setSidebarPermissions] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setSidebarPermissions({});
    if (!token) return;
    let active = true;
    resolveSidebarPermissions(token)
      .then((perms) => {
        if (active) setSidebarPermissions(perms);
      })
      .catch((error) => {
        console.error("Failed to resolve sidebar permissions:", error);
      });
    return () => {
      active = false;
    };
  }, [token]);

  if (!loading && !isAuthenticated) {
    redirect("/login");
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Spinner />
      </div>
    );
  }

  if (!isAuthenticated) return null;

  const userInfo = {
    name: user?.name || user?.username,
    email: user?.email,
    plan: "Free Plan",
  };

  return (
    <PluginProvider token={token}>
      <SidebarProvider>
        <DashboardContent user={userInfo} logout={logout} sidebarPermissions={sidebarPermissions}>
          {children}
        </DashboardContent>
      </SidebarProvider>
    </PluginProvider>
  );
}
