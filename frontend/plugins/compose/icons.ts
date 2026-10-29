import { Plus } from "lucide-react";

import { PLUGIN_ICONS } from "@/lib/icons/slots";

// The backend ComposePlugin declares its display and sidebar icon as "plus".
PLUGIN_ICONS.set("compose", [{ name: "plus", component: Plus }]);
