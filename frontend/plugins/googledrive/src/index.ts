import { PluginDefinition } from "@/lib/plugins/types";
import { GOOGLEDRIVE_PLUGIN_NAME } from "@/plugins/googledrive/src/constants";
// This plugin's contributions to the slots of core and of other plugins.
import "@/plugins/googledrive/src/slots/attachments";
import "@/plugins/googledrive/src/slots/icons";
import "@/plugins/googledrive/src/slots/settings";

// Display name and description are declared by the backend GoogleDrivePlugin
// and arrive via the user-plugins API.
export const googledrive: PluginDefinition = {
  name: GOOGLEDRIVE_PLUGIN_NAME,
  loadComponent: () => import("@/plugins/googledrive/src/pages/GoogleDrive"),
};
