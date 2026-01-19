"use client";

import "@/lib/plugins";
import { useAuth } from "@/lib/auth-context";
import { PluginProvider } from "@/lib/plugins/context";
import AppSidebar from "@/components/AppSidebar";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

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

  return (
    <PluginProvider token={token}>
      <div className="flex h-screen">
        <AppSidebar
          user={{
            name: user?.name || user?.username,
            email: user?.email,
            avatar: user?.avatar,
            plan: user?.plan || "Free Plan",
          }}
          onLogout={logout}
        />
        <main className="flex-1 overflow-auto bg-edly-gray-50">{children}</main>
      </div>
    </PluginProvider>
  );
}
