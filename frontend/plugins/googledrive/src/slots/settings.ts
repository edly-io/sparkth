import { SettingsListItem } from "@/lib/components/settings/SettingsListItem";
import { SETTINGS_ITEMS } from "@/lib/settings/slots";
import { GOOGLEDRIVE_PLUGIN_NAME } from "@/plugins/googledrive/src/constants";

// Google Drive's row on the settings page, with the config modal built from its backend config.
SETTINGS_ITEMS.set(GOOGLEDRIVE_PLUGIN_NAME, {
  listItem: SettingsListItem,
  loadConfigModal: () => import("@/lib/components/settings/ConfigModal"),
});
