"use client";

import { useParams } from "next/navigation";
import { getPlugin } from "@/lib/plugins";
import { usePlugin } from "@/lib/plugins/context";

export default function PluginLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const params = useParams();
  const pluginName = params?.pluginName as string;

  const pluginDef = getPlugin(pluginName);
  const { isEnabled } = usePlugin(pluginName);

  if (!pluginDef || !isEnabled) {
    return <>{children}</>;
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-auto">{children}</div>
    </div>
  );
}
