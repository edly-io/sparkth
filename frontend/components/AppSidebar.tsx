"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Settings,
  Loader2,
  ChevronDown,
  LogOut,
  User as UserIcon,
} from "lucide-react";
import { useState } from "react";
import { useEnabledPlugins } from "@/lib/plugins/context";
import Image from "next/image";

interface AppSidebarProps {
  user?: {
    name?: string;
    email?: string;
    avatar?: string;
    plan?: string;
  };
  basePath?: string;
  onLogout?: () => void;
  showPluginCount?: boolean;
  collapsible?: boolean;
}

export default function AppSidebar({
  user,
  basePath = "/dashboard",
  onLogout,
  showPluginCount = false,
  collapsible = false,
}: AppSidebarProps) {
  const pathname = usePathname();
  const { plugins, loading } = useEnabledPlugins();
  const [isPluginsExpanded, setIsPluginsExpanded] = useState(true);
  const [showUserMenu, setShowUserMenu] = useState(false);

  const isActiveRoute = (pluginName: string) => {
    const pluginPath = `${basePath}/${pluginName}`;
    return pathname === pluginPath || pathname?.startsWith(`${pluginPath}/`);
  };

  return (
    <div className="w-64 bg-white border-r flex flex-col h-screen">
      <div className="p-4 border-b">
        <Link
          href="/"
          className="flex items-center gap-2 hover:opacity-80 transition-opacity"
        >
          <div className="w-8 h-8 bg-blue-600 rounded flex items-center justify-center">
            <span className="text-white font-bold text-sm">S</span>
          </div>
          <span className="font-semibold text-lg text-gray-800">Sparkth</span>
        </Link>
      </div>

      <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
        <div className="flex items-center justify-between px-3 mb-2">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Plugins
          </p>
          {showPluginCount && plugins.length > 0 && (
            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-medium">
              {plugins.length}
            </span>
          )}
          {collapsible && (
            <button
              onClick={() => setIsPluginsExpanded(!isPluginsExpanded)}
              className="p-0.5 hover:bg-gray-100 rounded transition-colors"
              aria-label={
                isPluginsExpanded ? "Collapse plugins" : "Expand plugins"
              }
            >
              <ChevronDown
                className={`w-4 h-4 text-gray-500 transition-transform ${
                  isPluginsExpanded ? "" : "-rotate-90"
                }`}
              />
            </button>
          )}
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
            <Loader2 className="w-6 h-6 text-gray-400 animate-spin mb-2" />
            <p className="text-sm text-gray-500">Loading plugins...</p>
          </div>
        ) : (
          isPluginsExpanded && (
            <>
              {plugins.map((plugin) => (
                <PluginNavItem
                  key={plugin.name}
                  plugin={plugin}
                  basePath={basePath}
                  isActive={isActiveRoute(plugin.name)}
                />
              ))}

              <div className="pt-2 mt-2 border-t">
                <Link
                  href={`${basePath}/settings`}
                  className={`
                  flex items-center gap-3 px-3 py-2 rounded-lg transition-colors
                  ${
                    pathname === `${basePath}/settings`
                      ? "bg-blue-50 text-blue-600"
                      : "text-gray-700 hover:bg-gray-100"
                  }
                `}
                >
                  <Settings className="w-5 h-5 flex-shrink-0" />
                  <span className="font-medium">Plugin Settings</span>
                </Link>
              </div>
            </>
          )
        )}
      </nav>

      <div className="p-4 border-t bg-gray-50 relative">
        <button
          onClick={() => setShowUserMenu(!showUserMenu)}
          className="w-full flex items-center gap-3 hover:bg-gray-100 p-2 -m-2 rounded-lg transition-colors"
        >
          {user?.avatar ? (
            <Image
              src={user.avatar}
              alt={user.name || "User"}
              className="w-8 h-8 rounded-full object-cover"
            />
          ) : (
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center flex-shrink-0">
              <span className="text-sm text-white font-semibold">
                {user?.name?.charAt(0).toUpperCase() || "👤"}
              </span>
            </div>
          )}
          <div className="flex-1 min-w-0 text-left">
            <p className="text-sm font-medium text-gray-900 truncate">
              {user?.name || "User"}
            </p>
            <p className="text-xs text-gray-500 truncate">
              {user?.email || user?.plan || "Free Plan"}
            </p>
          </div>
          <ChevronDown className="w-4 h-4 text-gray-400 flex-shrink-0" />
        </button>

        {showUserMenu && (
          <div className="absolute bottom-full left-4 right-4 mb-2 bg-white border rounded-lg shadow-lg py-1">
            <Link
              href="/profile"
              className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100"
              onClick={() => setShowUserMenu(false)}
            >
              <UserIcon className="w-4 h-4" />
              Profile
            </Link>
            <Link
              href="/dashboard/settings"
              className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100"
              onClick={() => setShowUserMenu(false)}
            >
              <Settings className="w-4 h-4" />
              Settings
            </Link>
            {onLogout && (
              <>
                <div className="border-t my-1" />
                <button
                  onClick={() => {
                    setShowUserMenu(false);
                    onLogout();
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50"
                >
                  <LogOut className="w-4 h-4" />
                  Logout
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function PluginNavItem({
  plugin,
  basePath,
  isActive,
}: {
  plugin: {
    name: string;
    displayName: string;
    sidebarLabel?: string;
    description?: string;
  };
  basePath: string;
  isActive: boolean;
}) {
  const label = plugin.sidebarLabel || plugin.displayName;

  return (
    <Link
      href={`${basePath}/${plugin.name}`}
      className={`
        flex items-center gap-3 px-3 py-2 rounded-lg transition-colors
        ${
          isActive
            ? "bg-blue-50 text-blue-600"
            : "text-gray-700 hover:bg-gray-100"
        }
      `}
      title={plugin.description}
    >
      <div className="w-5 h-5 flex-shrink-0 rounded bg-gray-200 flex items-center justify-center">
        <span className="text-xs font-semibold text-gray-600">
          {label.charAt(0).toUpperCase()}
        </span>
      </div>
      <span className="font-medium truncate">{label}</span>
    </Link>
  );
}
