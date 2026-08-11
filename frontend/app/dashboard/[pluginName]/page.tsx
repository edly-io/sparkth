import PluginPageClient from "./page-client";
import { FRONTEND_PLUGIN_NAMES } from "@/lib/plugins/generated";

// Static routes come from the backend-declared frontend plugins; regenerate
// the list with `make frontend.build.plugins` after changing declarations.
export function generateStaticParams() {
  return FRONTEND_PLUGIN_NAMES.map((pluginName) => ({ pluginName }));
}

export default function PluginPage() {
  return <PluginPageClient />;
}
