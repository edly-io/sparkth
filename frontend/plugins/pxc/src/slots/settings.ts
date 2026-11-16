import { SettingsListItem } from "@/lib/components/settings/SettingsListItem";
import { SETTINGS_ITEMS } from "@/lib/settings/slots";
import { PXC_PLUGIN_NAME } from "@/plugins/pxc/src/constants";

// PXC's row on the settings page, with the config modal built from its backend config.
SETTINGS_ITEMS.set(PXC_PLUGIN_NAME, {
  listItem: SettingsListItem,
  loadConfigModal: () => import("@/lib/components/settings/ConfigModal"),
});
