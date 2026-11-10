import { Folder } from "lucide-react";

import { PLUGIN_ICONS } from "@/lib/icons/slots";

// The backend GoogleDrivePlugin declares its sidebar icon as "folder".
PLUGIN_ICONS.set("google-drive", [{ name: "folder", component: Folder }]);
