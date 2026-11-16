import { SettingsListItem } from "@/lib/components/settings/SettingsListItem";
import { SETTINGS_ITEMS } from "@/lib/settings/slots";
import { COMPOSE_PLUGIN_NAME } from "@/plugins/compose/src/constants";

// Compose's row on the settings page, with the config modal built from its backend config.
SETTINGS_ITEMS.set(COMPOSE_PLUGIN_NAME, {
  listItem: SettingsListItem,
  loadConfigModal: () => import("@/lib/components/settings/ConfigModal"),
});
