import { SettingsListItem } from "@/lib/components/settings/SettingsListItem";
import { SETTINGS_ITEMS } from "@/lib/settings/slots";
import { OPENEDX_PLUGIN_NAME } from "@/plugins/openedx/src/constants";

// Open edX's row on the settings page, with the config modal built from its backend config.
SETTINGS_ITEMS.set(OPENEDX_PLUGIN_NAME, {
  listItem: SettingsListItem,
  loadConfigModal: () => import("@/lib/components/settings/ConfigModal"),
});
