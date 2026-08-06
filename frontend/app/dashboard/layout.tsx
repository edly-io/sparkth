"use client";

import { useState, useEffect } from "react";
import "@/lib/plugins";
import { useAuth } from "@/lib/auth-context";
import { resolveNavPermissions } from "@/components/NavItem";
import { PluginProvider } from "@/lib/plugins/context";
import AppSidebar from "@/components/AppSidebar";
import MobileSidebar from "@/components/MobileSidebar";
import { SidebarProvider, useSidebar } from "@/lib/sidebar-context";
import { redirect } from "next/navigation";
import { Menu } from "lucide-react";
import { Spinner } from "@/components/Spinner";
import { Button } from "@/components/ui/Button";
import { SparkthLogo } from "@/components/SparkthLogo";
import { ThemeToggle } from "@/components/ThemeToggle";

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
  navPermissions,
}: {
  children: React.ReactNode;
  user: {
    name?: string;
    email?: string;
    avatar?: string;
    plan?: string;
  };
  logout: () => void;
  navPermissions: Record<string, boolean>;
}) {
  const { isCollapsed, toggleCollapsed } = useSidebar();

  return (
    <div className="flex flex-col h-screen">
      <MobileHeader />
      <div className="flex flex-1 overflow-hidden">
        <div className="hidden lg:block">
          <AppSidebar
            user={user}
            navPermissions={navPermissions}
            onLogout={logout}
            variant="desktop"
            isCollapsed={isCollapsed}
            onToggleCollapse={toggleCollapsed}
          />
        </div>
        <MobileSidebar user={user} navPermissions={navPermissions} onLogout={logout} />
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

  const [navPermissions, setNavPermissions] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setNavPermissions({});
    if (!token) return;
    let active = true;
    resolveNavPermissions(token)
      .then((perms) => {
        if (active) setNavPermissions(perms);
      })
      .catch((error) => {
        console.error("Failed to resolve nav permissions:", error);
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
        <DashboardContent user={userInfo} logout={logout} navPermissions={navPermissions}>
          {children}
        </DashboardContent>
      </SidebarProvider>
    </PluginProvider>
  );
}
