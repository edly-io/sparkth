// The frontend's plugins: loading every plugin's entry point runs its contributions to the slots,
// and every plugin that set itself in the PLUGINS slot is registered with core.
import { registerPlugin } from "@/core/plugins/registry";
import { PLUGINS } from "@/lib/plugins/slots";
import "@/app/pluginModules";

for (const plugin of PLUGINS.values()) registerPlugin(plugin);
