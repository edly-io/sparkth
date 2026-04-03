import { PluginDefinition } from "@/lib/plugins";
import ResourcesIcon from "./ResourcesIcon";

export const googleDrivePlugin: PluginDefinition = {
  name: "google-drive",
  displayName: "Google Drive",
  description: "All imported files from your connected plugins",
  isCore: true,
  category: "integration",
  loadComponent: () => import("./GoogleDrive"),
  showInSidebar: true,
  sidebarIcon: ResourcesIcon,
  sidebarLabel: "Resources",
  sidebarOrder: 2,
};
