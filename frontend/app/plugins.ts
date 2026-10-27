// The frontend's plugin list: importing each plugin's index.ts runs its contributions to core's
// slots, and a plugin with a page is registered with core.
import { registerPlugin } from "@/core/plugins/registry";
import { chatPlugin } from "@/plugins/chat";
import { googleDrivePlugin } from "@/plugins/google-drive";
import { pxcPlugin } from "@/plugins/pxc";
import { slackPlugin } from "@/plugins/slack";

registerPlugin(chatPlugin);
registerPlugin(googleDrivePlugin);
registerPlugin(pxcPlugin);
registerPlugin(slackPlugin);
