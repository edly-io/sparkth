// app/dashboard/[pluginName]/page.tsx
'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { getPlugin } from '@/lib/plugins';
import '@/lib/plugins';
import PluginRenderer from '@/components/PluginRenderer';

export default function PluginPage() {
  const pathname = usePathname();
  const router = useRouter();
  const { token, isAuthenticated } = useAuth();
  const [isEnabled, setIsEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [config, setConfig] = useState({});

  const pluginName = pathname?.split('/').filter(Boolean)[1] || '';

  const pluginDef = getPlugin(pluginName);

  useEffect(() => {
    console.log("pathname:", pathname);
    console.log("pluginName:", pluginName);
    
    if (!isAuthenticated) {
      router.push('/login');
      return;
    }

    async function checkPlugin() {
      if (!token) {
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
          const plugins = await response.json();
          console.log("Fetched plugins:", plugins);
          
          const userPlugin = plugins.find((p: any) => p.plugin_name === pluginName);
          console.log("Found user plugin:", userPlugin);
          
          if (userPlugin && userPlugin.enabled) {
            setIsEnabled(true);
            setConfig(userPlugin.config || {});
          }
        }
      } catch (error) {
        console.error('Failed to check plugin:', error);
      } finally {
        setLoading(false);
      }
    }

    if (pluginName) {
      checkPlugin();
    }
  }, [token, pluginName, router, isAuthenticated, pathname]);

  if (!pluginName) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900">Invalid URL</h2>
        </div>
      </div>
    );
  }

  if (!pluginDef) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900">Plugin not found</h2>
          <p className="text-gray-600 mt-2">No plugin registered with name: {pluginName}</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!isEnabled) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            Plugin Not Enabled
          </h2>
          <p className="text-gray-600 mb-4">
            {pluginDef.displayName} is not enabled for your account.
          </p>
          <Link
            href="/dashboard/settings/plugins"
            className="text-blue-600 hover:underline"
          >
            Enable it in settings
          </Link>
        </div>
      </div>
    );
  }

  return <PluginRenderer pluginDef={pluginDef} config={config} />;
}