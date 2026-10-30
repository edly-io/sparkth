import { PluginDefinition } from "@/lib/plugins/types";
// This plugin's contributions to core's slots.
import "./icons";
import "./settings";

export const SLACK_PLUGIN_PATH = "/dashboard/slack";

export const slackPlugin: PluginDefinition = {
  name: "slack",
  loadComponent: () => import("./SlackPlugin"),
};
