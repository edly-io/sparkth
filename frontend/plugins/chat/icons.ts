import { Plus } from "lucide-react";

import { PLUGIN_ICONS } from "@/lib/icons/slots";
import { setNamedSlotItems } from "@/lib/slots";

// The backend ChatPlugin declares its display and sidebar icon as "plus".
setNamedSlotItems(PLUGIN_ICONS, "chat", [{ name: "plus", component: Plus }]);
