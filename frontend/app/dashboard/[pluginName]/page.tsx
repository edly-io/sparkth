import PluginPageClient from "./page-client";

export function generateStaticParams() {
  return [{ pluginName: "chat-interface" }];
}

export default function PluginPage() {
  return <PluginPageClient />;
}
