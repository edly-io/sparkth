import { PluginDefinition } from "@/lib/plugins/types";
import { registerPluginIcon } from "@/lib/plugins/icons";
import SlackIcon from "./SlackIcon";

export const SLACK_PLUGIN_PATH = "/dashboard/slack";

// The backend Slack plugin declares its metadata with icon name "slack";
// the brand icon component itself ships with this frontend plugin.
registerPluginIcon("slack", SlackIcon);

export const slackPlugin: PluginDefinition = {
  name: "slack",
  loadComponent: () => import("./SlackPlugin"),
};
