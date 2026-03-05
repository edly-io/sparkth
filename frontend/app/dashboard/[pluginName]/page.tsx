import PluginPageClient from "./page-client";

export function generateStaticParams() {
  return [{ pluginName: "chat" }, { pluginName: "google-drive" }];
}

export default function PluginPage() {
  return <PluginPageClient />;
}
