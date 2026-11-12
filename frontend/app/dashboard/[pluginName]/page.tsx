import PluginPageClient from "./page-client";
import "@/app/plugins";
import { getAllPlugins } from "@/core/plugins/registry";

// One static page per plugin that registered with core, so the export builds a page for every
// plugin folder.
export function generateStaticParams() {
  return getAllPlugins().map((plugin) => ({ pluginName: plugin.name }));
}

export default function PluginPage() {
  return <PluginPageClient />;
}
