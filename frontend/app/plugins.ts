// The frontend's plugin list: importing each plugin's entry point runs its contributions to core's
// slots, and a plugin with a page is registered with core.
import { registerPlugin } from "@/core/plugins/registry";
import "@/plugins/canvas/src";
import { composePlugin } from "@/plugins/compose";
import { googleDrivePlugin } from "@/plugins/google-drive";
import "@/plugins/moodle/src";
import "@/plugins/openedx/src";
import { pxc } from "@/plugins/pxc/src";
import { slack } from "@/plugins/slack/src";

registerPlugin(composePlugin);
registerPlugin(googleDrivePlugin);
registerPlugin(pxc);
registerPlugin(slack);
