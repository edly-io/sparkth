// The barrel, not @/lib/plugins/registry — the registerPlugin() calls live in
// the barrel, so importing the leaf would return an empty registry.
import { getAllPlugins } from "@/lib/plugins";
import PluginPageClient from "./page-client";

export function generateStaticParams() {
  return getAllPlugins().map((plugin) => ({ pluginName: plugin.name }));
}

export default function PluginPage() {
  return <PluginPageClient />;
}
