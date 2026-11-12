import { PluginDefinition } from "@/lib/plugins/types";
import { PLUGINS } from "@/lib/plugins/slots";
import { SLACK_PLUGIN_NAME } from "@/plugins/slack/src/constants";
// This plugin's contributions to core's slots.
import "@/plugins/slack/src/slots/icons";
import "@/plugins/slack/src/slots/settings";

export const slack: PluginDefinition = {
  name: SLACK_PLUGIN_NAME,
  loadComponent: () => import("@/plugins/slack/src/pages/Slack"),
};

PLUGINS.set(slack.name, slack);
