"use client";

import { useParams, usePathname } from "next/navigation";
import Link from "next/link";
import { getPlugin } from "@/lib/plugins";
import { usePlugin } from "@/lib/plugins/context";
import { ChevronRight } from "lucide-react";

export default function PluginLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const params = useParams();
  const pathname = usePathname();
  const pluginName = params?.pluginName as string;

  const pluginDef = getPlugin(pluginName);
  const { isEnabled } = usePlugin(pluginName);

  if (!pluginDef || !isEnabled) {
    return <>{children}</>;
  }

  const currentRouteLabel = pluginDef.routes?.find(
    (r) =>
      pathname ===
      `${basePath}/${r.path.startsWith("/") ? r.path.slice(1) : r.path}`
  )?.label;

  const basePath = `/dashboard/${pluginName}`;
  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-3 bg-gray-50 border-b">
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <Link href="/dashboard" className="hover:text-gray-900">
            Dashboard
          </Link>
          <ChevronRight className="w-4 h-4" />
          <Link href={basePath} className="hover:text-gray-900">
            {pluginDef.displayName}
          </Link>
          {currentRouteLabel && (
            <>
              <ChevronRight className="w-4 h-4" />
              <span className="text-gray-900 font-medium">
                {currentRouteLabel}
              </span>
            </>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-auto">{children}</div>
    </div>
  );
}
