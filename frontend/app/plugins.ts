// The frontend's plugins: importing each plugin's entry point runs its contributions to the slots,
// and every plugin that set itself in the PLUGINS slot is registered with core.
import { registerPlugin } from "@/core/plugins/registry";
import { PLUGINS } from "@/lib/plugins/slots";
import "@/plugins/canvas/src";
import "@/plugins/compose/src";
import "@/plugins/googledrive/src";
import "@/plugins/moodle/src";
import "@/plugins/openedx/src";
import "@/plugins/pxc/src";
import "@/plugins/slack/src";

for (const plugin of PLUGINS.values()) registerPlugin(plugin);
