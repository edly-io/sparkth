// The frontend's plugin list: importing each plugin's index.ts runs its contributions to core's
// slots, and a plugin with a page is registered with core.
import { registerPlugin } from "@/core/plugins/registry";
import "@/plugins/canvas";
import { composePlugin } from "@/plugins/compose";
import { googleDrivePlugin } from "@/plugins/google-drive";
import "@/plugins/moodle";
import "@/plugins/openedx";
import { pxcPlugin } from "@/plugins/pxc";
import { slackPlugin } from "@/plugins/slack";

registerPlugin(composePlugin);
registerPlugin(googleDrivePlugin);
registerPlugin(pxcPlugin);
registerPlugin(slackPlugin);
