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
import { ComponentType, useState } from "react";
import { useEnabledPlugins } from "@/lib/plugins/context";
import Image from "next/image";
import { SparkthLogo } from "./SparkthLogo";
import { Button } from "@/components/ui/Button";

interface AppSidebarProps {
  user?: {
    name?: string;
    email?: string;
    avatar?: string;
    plan?: string;
  };
  basePath?: string;
  onLogout?: () => void;
}

export default function AppSidebar({
  user,
  basePath = "/dashboard",
  onLogout,
}: AppSidebarProps) {
  const pathname = usePathname();
  const { plugins, loading } = useEnabledPlugins();
  const [showUserMenu, setShowUserMenu] = useState(false);

  const isActiveRoute = (pluginName: string) => {
    const pluginPath = `${basePath}/${pluginName}`;
    return pathname === pluginPath || pathname?.startsWith(`${pluginPath}/`);
  };

  return (
    <div className="w-64 bg-card border-r border-border flex flex-col h-screen transition-colors">
      <div className="flex justify-center p-4 border-b border-border">
        <SparkthLogo />
      </div>

      <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
            <Loader2 className="w-6 h-6 text-muted animate-spin mb-2" />
            <p className="text-sm text-muted-foreground">Loading plugins...</p>
          </div>
        ) : (
          <>
            {plugins.map((plugin) => (
              <PluginNavItem
                key={plugin.name}
                plugin={plugin}
                basePath={basePath}
                isActive={isActiveRoute(plugin.name)}
              />
            ))}

            <div className="pt-2 mt-2">
              <Link
                href={`${basePath}/settings`}
                className={`
                  flex items-center gap-3 px-3 py-2 rounded-lg transition-colors text-foreground
                  ${
                    isActiveRoute("settings")
                      ? "bg-primary-100 dark:bg-primary-900/30"
                      : "hover:bg-surface-variant"
                  }
                `}
              >
                <Settings className="w-5 h-5 flex-shrink-0" />
                <span className="font-medium">My Plugins</span>
              </Link>
            </div>
          </>
        )}
      </nav>

      <div className="p-4 border-t border-border bg-surface-variant relative">
        <Button
          variant="ghost"
          onClick={() => setShowUserMenu(!showUserMenu)}
          className="w-full flex items-center gap-3 hover:bg-neutral-200 dark:hover:bg-neutral-700 p-2 -m-2"
        >
          {user?.avatar ? (
            <Image
              src={user.avatar}
              alt={user.name || "User"}
              width={32}
              height={32}
              className="w-8 h-8 rounded-full object-cover"
            />
          ) : (
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-error-400 to-error-600 flex items-center justify-center flex-shrink-0">
              <span className="text-sm text-white font-semibold">
                {user?.name?.charAt(0).toUpperCase() || "👤"}
              </span>
            </div>
          )}
          <div className="flex-1 min-w-0 text-left">
            <p className="text-sm font-medium text-foreground truncate">
              {user?.name || "User"}
            </p>
            <p className="text-xs text-muted-foreground truncate">
              {user?.email || user?.plan || "Free Plan"}
            </p>
          </div>
          <ChevronDown className="w-4 h-4 text-muted flex-shrink-0" />
        </Button>

        {showUserMenu && (
          <div className="absolute bottom-full left-4 right-4 mb-2 bg-card border border-border rounded-lg shadow-lg py-1">
            <Link
              href="/profile"
              className="flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-surface-variant"
              onClick={() => setShowUserMenu(false)}
            >
              <UserIcon className="w-4 h-4" />
              Profile
            </Link>
            <Link
              href="/dashboard/settings"
              className="flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-surface-variant"
              onClick={() => setShowUserMenu(false)}
            >
              <Settings className="w-4 h-4" />
              Settings
            </Link>
            {onLogout && (
              <>
                <div className="border-t border-border my-1" />
                <Button
                  variant="ghost"
                  onClick={() => {
                    setShowUserMenu(false);
                    onLogout();
                  }}
                  className="w-full flex items-center justify-start gap-2 px-3 py-2 text-sm text-error-600 dark:text-error-400 hover:bg-error-50 dark:hover:bg-error-900/30"
                >
                  <LogOut className="w-4 h-4" />
                  Logout
                </Button>
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
    sidebarIcon?: ComponentType<{ className?: string }>;
    description?: string;
  };
  basePath: string;
  isActive: boolean;
}) {
  const label = plugin.sidebarLabel || plugin.displayName;
  const Icon = plugin.sidebarIcon;

  return (
    <Link
      href={`${basePath}/${plugin.name}`}
      className={`
        flex items-center gap-3 px-3 py-2 rounded-lg transition-colors text-foreground
        ${isActive ? "bg-primary-100 dark:bg-primary-900/30" : "hover:bg-surface-variant"}
      `}
      title={plugin.description}
    >
      {Icon ? (
        <Icon className="w-5 h-5 flex-shrink-0" />
      ) : (
        <div className="w-5 h-5 flex-shrink-0 rounded bg-neutral-200 dark:bg-neutral-700 flex items-center justify-center">
          <span className="text-xs font-semibold text-muted-foreground">
            {label.charAt(0).toUpperCase()}
          </span>
        </div>
      )}
      <span className="font-medium truncate">{label}</span>
    </Link>
  );
}
