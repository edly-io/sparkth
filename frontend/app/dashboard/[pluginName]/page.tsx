import PluginPageClient from "./page-client";
import "@/app/plugins";
import { getAllPlugins } from "@/core/plugins/registry";

/**
 * One static page per plugin that registered with core, so the export builds a page for every
 * plugin folder.
 */
export function generateStaticParams() {
  return getAllPlugins().map((plugin) => ({ pluginName: plugin.name }));
}

/**
 * A name no plugin registered has no page, so its address shows the not-found page: the dev
 * server then answers it the way the export does, which builds no page for it.
 */
export const dynamicParams = false;

export default function PluginPage() {
  return <PluginPageClient />;
}
