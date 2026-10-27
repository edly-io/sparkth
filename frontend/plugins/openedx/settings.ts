import { SettingsListItem } from "@/lib/components/settings/SettingsListItem";
import { SETTINGS_ITEMS } from "@/lib/settings/slots";

// Open edX's row on the settings page, with the config modal built from its backend config.
SETTINGS_ITEMS.set("open-edx", [
  {
    listItem: SettingsListItem,
    loadConfigModal: () => import("@/lib/components/settings/ConfigModal"),
  },
]);
