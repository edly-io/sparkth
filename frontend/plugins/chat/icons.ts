import { Plus } from "lucide-react";

import { PLUGIN_ICONS } from "@/lib/icons/slots";

// The backend ChatPlugin declares its display and sidebar icon as "plus".
PLUGIN_ICONS.set("chat", [{ name: "plus", component: Plus }]);
