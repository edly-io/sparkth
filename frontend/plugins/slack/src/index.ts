import { PluginDefinition } from "@/lib/plugins/types";
// This plugin's contributions to core's slots.
import "@/plugins/slack/src/slots/icons";
import "@/plugins/slack/src/slots/settings";

export const slack: PluginDefinition = {
  name: "slack",
  loadComponent: () => import("@/plugins/slack/src/pages/Slack"),
};
