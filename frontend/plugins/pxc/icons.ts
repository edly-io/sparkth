import { Blocks } from "lucide-react";

import { PLUGIN_ICONS } from "@/lib/icons/slots";
import { setNamedSlotItems } from "@/lib/slots";

// The backend PxcPlugin declares its display and sidebar icon as "blocks".
setNamedSlotItems(PLUGIN_ICONS, "pxc", [{ name: "blocks", component: Blocks }]);
