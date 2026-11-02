import { Blocks } from "lucide-react";

import { PLUGIN_ICONS } from "@/lib/icons/slots";

// The backend PxcPlugin declares its display and sidebar icon as "blocks".
PLUGIN_ICONS.set("pxc", [{ name: "blocks", component: Blocks }]);
