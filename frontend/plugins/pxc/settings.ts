import { SettingsListItem } from "@/lib/components/settings/SettingsListItem";
import { SETTINGS_ITEMS } from "@/lib/settings/slots";

// PXC's row on the settings page, with the config modal built from its backend config.
SETTINGS_ITEMS.set("pxc", {
  listItem: SettingsListItem,
  loadConfigModal: () => import("@/lib/components/settings/ConfigModal"),
});
