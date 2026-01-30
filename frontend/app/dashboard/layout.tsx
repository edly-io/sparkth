"use client";

import "@/lib/plugins";
import { useAuth } from "@/lib/auth-context";
import { PluginProvider } from "@/lib/plugins/context";
import AppSidebar from "@/components/AppSidebar";
import MobileSidebar from "@/components/MobileSidebar";
import { SidebarProvider, useSidebar } from "@/lib/sidebar-context";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Menu } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { SparkthLogo } from "@/components/SparkthLogo";
import { ThemeToggle } from "@/components/ThemeToggle";

function MobileHeader() {
  const { toggle } = useSidebar();

  return (
    <div className="lg:hidden flex items-center justify-between px-4 py-3 border-b border-border bg-card">
      <Button
        variant="ghost"
        size="icon"
        onClick={toggle}
        aria-label="Open menu"
      >
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
}: {
  children: React.ReactNode;
  user: {
    name?: string;
    email?: string;
    avatar?: string;
    plan?: string;
  };
  logout: () => void;
}) {
  const { isCollapsed, toggleCollapsed } = useSidebar();

  return (
    <div className="flex flex-col h-screen">
      <MobileHeader />
      <div className="flex flex-1 overflow-hidden">
        {/* Desktop sidebar - hidden on mobile/tablet */}
        <div className="hidden lg:block">
          <AppSidebar
            user={user}
            onLogout={logout}
            variant="desktop"
            isCollapsed={isCollapsed}
            onToggleCollapse={toggleCollapsed}
          />
        </div>

        {/* Mobile sidebar drawer */}
        <MobileSidebar user={user} onLogout={logout} />

        {/* Main content */}
        <main className="flex-1 overflow-auto bg-background">{children}</main>
      </div>
    </div>
  );
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { token, user, isAuthenticated, loading, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.push("/login");
    }
  }, [loading, isAuthenticated, router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  const userInfo = {
    name: user?.name || user?.username,
    email: user?.email,
    avatar: user?.avatar,
    plan: user?.plan || "Free Plan",
  };

  return (
    <PluginProvider token={token}>
      <SidebarProvider>
        <DashboardContent user={userInfo} logout={logout}>
          {children}
        </DashboardContent>
      </SidebarProvider>
    </PluginProvider>
  );
}
