// The frontend's plugin list: importing this module registers each plugin with core.
import { registerPlugin } from "@/core/plugins/registry";
import { chatPlugin, googleDrivePlugin, pxcPlugin, slackPlugin } from "@/plugins";

registerPlugin(chatPlugin);
registerPlugin(googleDrivePlugin);
registerPlugin(pxcPlugin);
registerPlugin(slackPlugin);
