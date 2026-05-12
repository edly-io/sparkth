import { PluginDefinition } from "@/lib/plugins";
import SlackIcon from "./SlackIcon";

export const SLACK_PLUGIN_PATH = "/dashboard/slack";

export const slackPlugin: PluginDefinition = {
  name: "slack",
  displayName: "Slack TA Bot",
  description: "Answer student questions in Slack from your course materials",
  isCore: true,
  category: "integration",
  loadComponent: () => import("./SlackPlugin"),
  loadSettingsComponent: () => import("./components/SlackConfigModal"),
  showInSidebar: true,
  sidebarIcon: SlackIcon,
  sidebarLabel: "Slack TA Bot",
  sidebarOrder: 3,
};
