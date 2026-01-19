import { PluginDefinition } from "@/lib/plugins";
import { PlusIcon } from "lucide-react";

export const chatPlugin: PluginDefinition = {
  name: "chat-interface",
  displayName: "Create Course",
  description: "Transform your resources into courses with AI",
  isCore: true,

  loadComponent: () => import("./ChatInterface"),

  showInSidebar: true,
  sidebarIcon: PlusIcon,
  sidebarLabel: "Create Course",
  sidebarOrder: 1,
};
