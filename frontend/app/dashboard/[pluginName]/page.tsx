import PluginPageClient from "./page-client";

export function generateStaticParams() {
  return [
    { pluginName: "chat-interface" },
    { pluginName: "google-drive" },
  ];
}

export default function PluginPage() {
  return <PluginPageClient />;
}
