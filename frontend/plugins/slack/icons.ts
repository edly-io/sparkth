import { PLUGIN_ICONS } from "@/lib/icons/slots";
import { setNamedSlotItems } from "@/lib/slots";
import SlackIcon from "./SlackIcon";

// The backend Slack plugin declares its metadata with icon name "slack";
// the brand icon component itself ships with this frontend plugin.
setNamedSlotItems(PLUGIN_ICONS, "slack", [{ name: "slack", component: SlackIcon }]);
