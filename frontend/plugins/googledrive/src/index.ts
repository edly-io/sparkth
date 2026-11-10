import { PluginDefinition } from "@/lib/plugins/types";
// This plugin's contributions to the slots of core and of other plugins.
import "@/plugins/googledrive/src/slots/attachments";
import "@/plugins/googledrive/src/slots/icons";
import "@/plugins/googledrive/src/slots/settings";

// Display name and description are declared by the backend GoogleDrivePlugin
// and arrive via the user-plugins API.
export const googledrive: PluginDefinition = {
  name: "google-drive",
  loadComponent: () => import("@/plugins/googledrive/src/routes/GoogleDrive"),
};
