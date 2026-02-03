"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Settings,
  Loader2,
  ChevronDown,
  LogOut,
  User as UserIcon,
  X,
  PanelLeftClose,
  PanelLeft,
} from "lucide-react";
import { ComponentType } from "react";
import { useEnabledPlugins } from "@/lib/plugins/context";
import Image from "next/image";
import { SparkthLogo } from "./SparkthLogo";
import { Button } from "@/components/ui/Button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/Tooltip";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/Popover";

interface AppSidebarProps {
  user?: {
    name?: string;
    email?: string;
    avatar?: string;
    plan?: string;
  };
  basePath?: string;
  onLogout?: () => void;
  variant?: "desktop" | "mobile";
  onNavigate?: () => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

export default function AppSidebar({
  user,
  basePath = "/dashboard",
  onLogout,
  variant = "desktop",
  onNavigate,
  isCollapsed = false,
  onToggleCollapse,
}: AppSidebarProps) {
  const pathname = usePathname();
  const { plugins, loading } = useEnabledPlugins();

  const isActiveRoute = (pluginName: string) => {
    const pluginPath = `${basePath}/${pluginName}`;
    return pathname === pluginPath || pathname?.startsWith(`${pluginPath}/`);
  };

  const handleNavClick = () => {
    if (onNavigate) {
      onNavigate();
    }
  };

  const sidebarWidth = variant === "mobile" ? "w-full" : isCollapsed ? "w-16" : "w-64";
  const isCollapsedDesktop = isCollapsed && variant === "desktop";

  const handleSidebarClick = (e: React.MouseEvent) => {
    // Only expand if collapsed on desktop and clicking empty area
    if (isCollapsedDesktop && onToggleCollapse) {
      // Don't expand if clicking on interactive elements
      const target = e.target as HTMLElement;
      if (target.closest('a, button')) return;
      onToggleCollapse();
    }
  };

  return (
    <div
      className={`${sidebarWidth} bg-card border-r border-border flex flex-col h-screen transition-all duration-300 ${isCollapsedDesktop ? "cursor-e-resize" : ""}`}
      onClick={handleSidebarClick}
    >
      {/* Header - min-h-[57px] matches ChatInterface header height */}
      <div className={`flex mb-4 items-center min-h-[57px] border-border overflow-hidden ${variant === "mobile" ? "px-2 justify-between" : "px-2 justify-between"}`}>
        {variant === "mobile" ? (
          <>
            <SparkthLogo size={32} iconOnly />
            <Button
              variant="ghost"
              size="icon"
              onClick={onNavigate}
              aria-label="Close sidebar"
            >
              <X className="h-5 w-5" />
            </Button>
          </>
        ) : (
          <>
            {isCollapsed ? (
              onToggleCollapse && (
                <Tooltip>
                  <TooltipTrigger>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={onToggleCollapse}
                      aria-label="Open sidebar"
                      className="group relative flex-shrink-0"
                    >
                      <span className="group-hover:opacity-0 transition-opacity duration-200 absolute inset-0 flex items-center justify-center">
                        <SparkthLogo size={32} iconOnly />
                      </span>
                      <PanelLeft className="h-5 w-5 opacity-0 group-hover:opacity-100 transition-opacity duration-200" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="right" sideOffset={8}>
                    Open sidebar
                  </TooltipContent>
                </Tooltip>
              )
            ) : (
              <>
                <div className="ml-2">
                  <SparkthLogo size={32} iconOnly />
                </div>
                {onToggleCollapse && (
                  <Tooltip>
                    <TooltipTrigger>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={onToggleCollapse}
                        aria-label="Close sidebar"
                        className="flex-shrink-0"
                      >
                        <PanelLeftClose className="h-5 w-5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="right" sideOffset={8}>
                      Close sidebar
                    </TooltipContent>
                  </Tooltip>
                )}
              </>
            )}
          </>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-2 space-y-1.5 overflow-y-auto">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
            <Loader2 className="w-6 h-6 text-muted animate-spin mb-2" />
            {!isCollapsed && <p className="text-sm text-muted-foreground">Loading plugins...</p>}
          </div>
        ) : (
          <>
            {plugins.map((plugin) => (
              <PluginNavItem
                key={plugin.name}
                plugin={plugin}
                basePath={basePath}
                isActive={isActiveRoute(plugin.name)}
                onClick={handleNavClick}
                isCollapsed={isCollapsed && variant === "desktop"}
              />
            ))}

            <div className="pt-3 mt-3">
              <Link
                href={`${basePath}/settings`}
                onClick={handleNavClick}
                className={`
                  flex items-center gap-3 px-3 py-2 min-h-[40px] rounded-lg transition-colors
                  ${isCollapsed && variant === "desktop" ? "justify-center" : ""}
                  ${
                    isActiveRoute("settings")
                      ? "bg-primary-500/15 text-primary-600 dark:text-primary-400 border-l-3 border-primary-500"
                      : "text-foreground hover:bg-surface-variant"
                  }
                `}
                title={isCollapsed ? "My Plugins" : undefined}
              >
                <Settings className="w-5 h-5 flex-shrink-0" />
                {!(isCollapsed && variant === "desktop") && <span className="font-medium">My Plugins</span>}
              </Link>
            </div>
          </>
        )}
      </nav>

      {/* User menu */}
      <div className={`p-3 border-t border-border ${isCollapsed && variant === "desktop" ? "flex justify-center" : ""}`}>
        <Popover>
          <PopoverTrigger asChild>
            <Button
              variant="ghost"
              className={`flex items-center gap-3 hover:bg-neutral-200 dark:hover:bg-neutral-700 min-h-[44px] ${isCollapsed && variant === "desktop" ? "w-auto p-2" : "w-full p-2"}`}
              title={isCollapsed ? user?.name || "User" : undefined}
            >
              {user?.avatar ? (
                <Image
                  src={user.avatar}
                  alt={user.name || "User"}
                  width={32}
                  height={32}
                  className="w-8 h-8 rounded-full object-cover flex-shrink-0"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-error-400 to-error-600 flex items-center justify-center flex-shrink-0">
                  <span className="text-sm text-white font-semibold">
                    {user?.name?.charAt(0).toUpperCase() || "👤"}
                  </span>
                </div>
              )}
              {!(isCollapsed && variant === "desktop") && (
                <>
                  <div className="flex-1 min-w-0 text-left">
                    <p className="text-sm font-medium text-foreground truncate">
                      {user?.name || "User"}
                    </p>
                    <p className="text-xs text-muted-foreground truncate">
                      {user?.plan || "Free Plan"}
                    </p>
                  </div>
                  <ChevronDown className="w-4 h-4 text-muted flex-shrink-0" />
                </>
              )}
            </Button>
          </PopoverTrigger>
          <PopoverContent side="top" align="start" sideOffset={20} className="w-52 p-2">
            <Link
              href="/profile"
              className="flex items-center gap-3 px-3 py-2 min-h-[40px] text-sm text-foreground hover:bg-surface-variant rounded-lg"
              onClick={handleNavClick}
            >
              <UserIcon className="w-4 h-4 flex-shrink-0" />
              <span className="truncate">Profile</span>
            </Link>
            <Link
              href="/dashboard/settings"
              className="flex items-center gap-3 px-3 py-2 min-h-[40px] text-sm text-foreground hover:bg-surface-variant rounded-lg"
              onClick={handleNavClick}
            >
              <Settings className="w-4 h-4 flex-shrink-0" />
              <span className="truncate">Settings</span>
            </Link>
            {onLogout && (
              <>
                <div className="border-t border-border my-2" />
                <Button
                  variant="ghost"
                  onClick={onLogout}
                  className="w-full flex items-center justify-start gap-3 px-3 py-2 min-h-[40px] text-sm text-error-600 dark:text-error-400 hover:bg-error-50 dark:hover:bg-error-900/30 rounded-lg"
                >
                  <LogOut className="w-4 h-4 flex-shrink-0" />
                  <span className="truncate">Logout</span>
                </Button>
              </>
            )}
          </PopoverContent>
        </Popover>
      </div>
    </div>
  );
}

function PluginNavItem({
  plugin,
  basePath,
  isActive,
  onClick,
  isCollapsed,
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
  onClick?: () => void;
  isCollapsed?: boolean;
}) {
  const label = plugin.sidebarLabel || plugin.displayName;
  const Icon = plugin.sidebarIcon;

  return (
    <Link
      href={`${basePath}/${plugin.name}`}
      onClick={onClick}
      className={`
        flex items-center gap-3 px-3 py-2 min-h-[40px] rounded-lg transition-colors
        ${isCollapsed ? "justify-center" : ""}
        ${isActive ? "bg-primary-500/15 text-primary-600 dark:text-primary-400 border-l-3 border-primary-500" : "text-foreground hover:bg-surface-variant"}
      `}
      title={isCollapsed ? label : plugin.description}
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
      {!isCollapsed && <span className="font-medium truncate">{label}</span>}
    </Link>
  );
}
