// Adds this plugin's permission names to the vocabulary permission checks are typed against.

export {};

declare module "@/lib/permissions/names" {
  interface PluginPermissions {
    googledrive: "googledrive.read" | "googledrive.sync" | "googledrive.delete";
  }
}
