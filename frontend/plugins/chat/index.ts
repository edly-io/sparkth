import { PluginDefinition } from "@/lib/plugins";

// Display name, description, icon, and sidebar entry are declared by the
// backend ChatPlugin and arrive via the user-plugins API.
export const chatPlugin: PluginDefinition = {
  name: "chat",
  loadComponent: () => import("./ChatInterface"),
  loadSettingsComponent: () => import("./components/ChatConfigModal"),
};
