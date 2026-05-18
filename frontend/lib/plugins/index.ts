import { registerPlugin } from "./registry";
import { chatPlugin, googleDrivePlugin, slackPlugin } from "@/plugins";

registerPlugin(chatPlugin);
registerPlugin(googleDrivePlugin);
registerPlugin(slackPlugin);

export * from "./registry";
export * from "./types";
export * from "./usePlugins";
