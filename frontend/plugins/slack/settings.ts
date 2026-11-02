import { SettingsListItem } from "@/lib/components/settings/SettingsListItem";
import { SETTINGS_ITEMS } from "@/lib/settings/slots";

// Slack's row on the settings page. Its config modal adds Slack's own control for the
// `allowed_sources` field, which the backend marks with the `doc-sources` widget hint.
SETTINGS_ITEMS.set("slack", {
  listItem: SettingsListItem,
  loadConfigModal: () => import("./SlackConfigModal"),
});
