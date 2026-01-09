'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/lib/auth-context';
import { useRouter } from 'next/navigation';
import { getPluginsByNames } from '@/lib/plugins';
import AppSidebar from '@/components/AppSidebar';
import { PluginDefinition } from '@/lib/plugins/types';
import '@/lib/plugins';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { token, isAuthenticated } = useAuth();
  const router = useRouter();
  const [sidebarPlugins, setSidebarPlugins] = useState<PluginDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (mounted && !isAuthenticated) {
      router.push('/login');
    }
  }, [mounted, isAuthenticated, router]);

  useEffect(() => {
    async function loadPlugins() {
      if (!token || !isAuthenticated) {
        setLoading(false);
        return;
      }

      try {
        const response = await fetch('/api/v1/user-plugins/', {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (response.ok) {
          const enabledPlugins = await response.json();
          const enabledPluginNames = enabledPlugins
            .filter((p: any) => p.enabled)
            .map((p: any) => p.plugin_name);
          
          const plugins = getPluginsByNames(enabledPluginNames);
          
          const sidebar = plugins
            .filter(p => p.showInSidebar)
            .sort((a, b) => (a.sidebarOrder || 99) - (b.sidebarOrder || 99));
          
          setSidebarPlugins(sidebar);
        }
      } catch (error) {
        console.error('Failed to load plugins:', error);
      } finally {
        setLoading(false);
      }
    }

    if (isAuthenticated) {
      loadPlugins();
    }
  }, [token, isAuthenticated]);

  if (!mounted || loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      <AppSidebar plugins={sidebarPlugins} />
      <main className="flex-1 overflow-hidden">
        {children}
      </main>
    </div>
  );
}