import { PluginDefinition } from "@/lib/plugins/types";
// This plugin's contributions to the slots of core and of other plugins.
import "@/plugins/google-drive/attachments";
import "@/plugins/google-drive/settings";

// Display name and description are declared by the backend GoogleDrivePlugin
// and arrive via the user-plugins API.
export const googleDrivePlugin: PluginDefinition = {
  name: "google-drive",
  loadComponent: () => import("./GoogleDrive"),
};
