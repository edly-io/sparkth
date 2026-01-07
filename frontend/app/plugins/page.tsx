"use client";

import { useCallback, useEffect, useState } from "react";
import { getUserPlugins, UserPlugin } from "@/lib/user-plugins";
import PluginCard from "@/components/plugin/Card";
import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import SparkthHeader from "@/components/SparkthHeader";

export default function PluginsPage() {
  const { token, isAuthenticated, logout } = useAuth();
  const router = useRouter();

  const [plugins, setPlugins] = useState<UserPlugin[]>([]);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);

  const loadPlugins = useCallback(async () => {
    if (!token) return;

    try {
      const plugins = await getUserPlugins(token);
      setPlugins(plugins);
    } catch (error) {
      alert(error);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (mounted && !isAuthenticated) {
      router.replace("/login");
    }
  }, [mounted, isAuthenticated, router]);

  useEffect(() => {
    if (mounted && isAuthenticated) {
      loadPlugins();
    }
  }, [mounted, isAuthenticated, loadPlugins]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading plugins...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <SparkthHeader isAuthenticated={isAuthenticated} logout={logout} />

      <div className="max-w-6xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Plugins</h1>
            <p className="mt-2 text-sm text-gray-600">
              Manage your system integrations
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
          <div className="bg-white rounded-lg shadow-sm p-4">
            <div className="text-sm text-gray-600">Total Plugins</div>
            <div className="text-2xl font-bold text-gray-900">
              {plugins.length}
            </div>
          </div>
          <div className="bg-white rounded-lg shadow-sm p-4">
            <div className="text-sm text-gray-600">Enabled</div>
            <div className="text-2xl font-bold text-green-600">
              {plugins.filter((p) => p.enabled).length}
            </div>
          </div>
          <div className="bg-white rounded-lg shadow-sm p-4">
            <div className="text-sm text-gray-600">Disabled</div>
            <div className="text-2xl font-bold text-gray-600">
              {plugins.filter((p) => !p.enabled).length}
            </div>
          </div>
        </div>

        {plugins.length > 0 ? (
          <div className="grid gap-6">
            {plugins.map((plugin) => (
              <PluginCard
                key={plugin.plugin_name}
                plugin={plugin}
                onUpdate={loadPlugins}
              />
            ))}
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow-sm p-12 text-center">
            <p className="text-gray-500">No plugins found</p>
          </div>
        )}
      </div>
    </div>
  );
}
