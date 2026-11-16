// Adds this plugin's permission names to the vocabulary permission checks are typed against.

export {};

declare module "@/lib/permissions/names" {
  interface PluginPermissions {
    compose: "compose.conversation.read" | "compose.conversation.write";
  }
}
