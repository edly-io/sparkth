import { registerPlugin } from "./registry";
import { chatPlugin, googleDrivePlugin } from "@/plugins";

registerPlugin(chatPlugin);
registerPlugin(googleDrivePlugin);

export * from "./registry";
export * from "./types";
export * from "./usePlugins";
