import { PluginDefinition } from "@/lib/plugins/types";

// Display name and description are declared by the backend GoogleDrivePlugin
// and arrive via the user-plugins API.
export const googleDrivePlugin: PluginDefinition = {
  name: "google-drive",
  loadComponent: () => import("./GoogleDrive"),
};
