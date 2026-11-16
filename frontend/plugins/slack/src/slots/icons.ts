import { PLUGIN_ICONS } from "@/lib/icons/slots";
import { SLACK_PLUGIN_NAME } from "@/plugins/slack/src/constants";
import SlackIcon from "@/plugins/slack/src/components/ui/SlackIcon";

// The backend Slack plugin declares its metadata with icon name "slack";
// the brand icon component itself ships with this frontend plugin.
PLUGIN_ICONS.set(SLACK_PLUGIN_NAME, [{ name: "slack", component: SlackIcon }]);
