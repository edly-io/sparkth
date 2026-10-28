import { PLUGIN_ICONS } from "@/lib/icons/slots";
import SlackIcon from "./SlackIcon";

// The backend Slack plugin declares its metadata with icon name "slack";
// the brand icon component itself ships with this frontend plugin.
PLUGIN_ICONS.set("slack", [{ name: "slack", component: SlackIcon }]);
