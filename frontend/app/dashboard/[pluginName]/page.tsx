import PluginPageClient from "./page-client";

export function generateStaticParams() {
  return [{ pluginName: "chat" }];
}

export default function PluginPage() {
  return <PluginPageClient />;
}
