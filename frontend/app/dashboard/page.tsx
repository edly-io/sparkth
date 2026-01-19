"use client";

import { useEnabledPlugins } from "@/lib/plugins/context";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

export default function DashboardPage() {
  const { plugins, loading } = useEnabledPlugins();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold text-edly-gray-900 mb-2">
          Dashboard
        </h1>
        <p className="text-edly-gray-600 mb-8">Manage your enabled plugins</p>

        {plugins.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-edly-gray-600 mb-4">No plugins enabled yet.</p>
            <Link
              href="/dashboard/settings"
              className="inline-block px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 transition-colors"
            >
              Browse Plugins
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {plugins.map((plugin) => {
              const Icon = plugin.icon;
              return (
                <Link
                  key={plugin.name}
                  href={`/dashboard/${plugin.name}`}
                  className="block p-6 bg-white rounded-lg border border-gray-200 hover:border-primary-500 hover:shadow-md transition-all"
                >
                  <div className="flex items-start justify-between mb-3">
                    {Icon ? (
                      <div className="p-2 bg-primary-50 rounded-lg">
                        <Icon className="w-6 h-6 text-edly-blue-600" />
                      </div>
                    ) : (
                      <div className="w-10 h-10 bg-edly-gray-100 rounded-lg flex items-center justify-center">
                        <span className="text-lg font-bold text-edly-gray-600">
                          {plugin.displayName.charAt(0)}
                        </span>
                      </div>
                    )}
                    <ArrowRight className="w-5 h-5 text-edly-gray-400" />
                  </div>
                  <h3 className="text-lg font-semibold text-edly-gray-900 mb-1">
                    {plugin.displayName}
                  </h3>
                  <p className="text-sm text-edly-gray-600 line-clamp-2">
                    {plugin.description || "No description available"}
                  </p>
                  {plugin.category && (
                    <span className="inline-block mt-3 px-2 py-1 text-xs bg-edly-gray-100 text-edly-gray-600 rounded">
                      {plugin.category}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
