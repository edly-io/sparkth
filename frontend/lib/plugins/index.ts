import { registerPlugin } from "./registry";
import { chatPlugin } from "@/plugins";

registerPlugin(chatPlugin);

export * from "./registry";
export * from "./types";
export * from "./usePlugins";
