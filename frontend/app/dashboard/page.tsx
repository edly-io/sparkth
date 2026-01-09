'use client';

import { useAuth } from '@/lib/auth-context';
import { usePlugins } from '@/lib/plugins/usePlugins';
import Link from 'next/link';

export default function DashboardPage() {
  const { token } = useAuth();
  const { enabledPlugins, loading } = usePlugins(token);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-6">Dashboard</h1>
      
      {enabledPlugins.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {enabledPlugins.map((plugin) => (
            <Link
              key={plugin.name}
              href={`/dashboard/${plugin.name}`}
              className="block p-6 bg-white rounded-lg shadow-sm border hover:border-blue-500 hover:shadow-md transition"
            >
              <div className="flex items-center gap-3 mb-2">
                <h2 className="text-xl font-semibold">{plugin.displayName}</h2>
              </div>
              {plugin.description && (
                <p className="text-gray-600 text-sm">{plugin.description}</p>
              )}
            </Link>
          ))}
        </div>
      ) : (
        <div className="bg-white p-12 rounded-lg shadow-sm text-center">
          <p className="text-gray-600 mb-4">No plugins enabled</p>
          <Link
            href="/dashboard/settings/plugins"
            className="text-blue-600 hover:underline"
          >
            Enable plugins in settings
          </Link>
        </div>
      )}
    </div>
  );
}
