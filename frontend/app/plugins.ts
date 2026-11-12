// The frontend's plugin list: importing each plugin's entry point runs its contributions to core's
// slots, and a plugin with a page is registered with core.
import { registerPlugin } from "@/core/plugins/registry";
import "@/plugins/canvas/src";
import { compose } from "@/plugins/compose/src";
import { googledrive } from "@/plugins/googledrive/src";
import "@/plugins/moodle/src";
import "@/plugins/openedx/src";
import { pxc } from "@/plugins/pxc/src";
import { slack } from "@/plugins/slack/src";

registerPlugin(compose);
registerPlugin(googledrive);
registerPlugin(pxc);
registerPlugin(slack);
