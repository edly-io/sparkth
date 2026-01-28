import { PluginDefinition } from "@/lib/plugins";
import GoogleDriveIcon from "./GoogleDriveIcon";

export const googleDrivePlugin: PluginDefinition = {
  name: "google-drive",
  displayName: "Google Drive",
  description: "Sync and manage your Google Drive files",
  isCore: true,
  category: "integration",

  loadComponent: () => import("./GoogleDrive"),

  showInSidebar: true,
  sidebarIcon: GoogleDriveIcon,
  sidebarLabel: "Google Drive",
  sidebarOrder: 2,
};
