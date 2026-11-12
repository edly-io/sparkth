import { Blocks } from "lucide-react";

import { PLUGIN_ICONS } from "@/lib/icons/slots";
import { PXC_PLUGIN_NAME } from "@/plugins/pxc/src/constants";

// The backend PxcPlugin declares its display and sidebar icon as "blocks".
PLUGIN_ICONS.set(PXC_PLUGIN_NAME, [{ name: "blocks", component: Blocks }]);
