import { Plus } from "lucide-react";

import { PLUGIN_ICONS } from "@/lib/icons/slots";
import { COMPOSE_PLUGIN_NAME } from "@/plugins/compose/src/constants";

// The backend ComposePlugin declares its display and sidebar icon as "plus".
PLUGIN_ICONS.set(COMPOSE_PLUGIN_NAME, [{ name: "plus", component: Plus }]);
