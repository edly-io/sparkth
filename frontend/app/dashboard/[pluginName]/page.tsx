import PluginPageClient from "./page-client";

export function generateStaticParams() {
  return [{ pluginName: "chat" }, { pluginName: "google-drive" }, { pluginName: "slack" }];
}

export default function PluginPage() {
  return <PluginPageClient />;
}
