import { PluginDefinition } from "@/lib/plugins";
// Imported from the leaf module (not the @/lib/plugins barrel) to avoid a
// runtime import cycle: the barrel imports @/plugins, which imports this file.
import { registerPluginIcon } from "@/lib/plugins/icons";
import SlackIcon from "./SlackIcon";

export const SLACK_PLUGIN_PATH = "/dashboard/slack";

// The backend Slack plugin declares its metadata with icon name "slack";
// the brand icon component itself ships with this frontend plugin.
registerPluginIcon("slack", SlackIcon);

export const slackPlugin: PluginDefinition = {
  name: "slack",
  loadComponent: () => import("./SlackPlugin"),
  loadSettingsComponent: () => import("./components/SlackConfigModal"),
};
