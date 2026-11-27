// Adds this plugin's permission names to the vocabulary permission checks are typed against.

export {};

declare module "@/lib/permissions/names" {
  interface PluginPermissions {
    pxc:
      | "pxc.activity.read"
      | "pxc.activity.play"
      | "pxc.activity.edit"
      | "pxc.activity.update"
      | "pxc.activity.delete"
      | "pxc.activity.place";
  }
}
